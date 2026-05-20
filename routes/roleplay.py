import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from services.question_generation_service import generate_question
from services.tts_service import text_to_speech
from services.speech_service import speech_to_text
from services.evaluation_service import evaluate_answer
from services.vad_service import VADProcessor
from services.auth_service import decode_access_token
from services.llm_service import client as openai_client
from database.connections import get_connection

router = APIRouter()

_executor = ThreadPoolExecutor()


# ── Scenario / character helpers ──────────────────────────────────────────────

def _scenario_system(scenario: str) -> str:
    return (
        f"You are playing the role of: {scenario}.\n"
        "Stay fully in character for the entire conversation.\n"
        "Respond exactly as this character would in real life — natural, authentic, "
        "emotional and specific to the situation.\n"
        "Keep every response to 1–3 sentences. Be concise.\n"
        "Never break character. Never give scores, coaching tips, or meta-commentary.\n"
        "React authentically to whatever the other person says."
    )


def _scenario_opening(scenario: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _scenario_system(scenario)},
            {"role": "user",   "content": "Begin. Deliver your opening line as this character. Just the line — nothing else."}
        ],
        temperature=0.85
    )
    return resp.choices[0].message.content.strip()


def _scenario_reply(scenario: str, history: list) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": _scenario_system(scenario)}] + history,
        temperature=0.85
    )
    return resp.choices[0].message.content.strip()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/roleplay")
async def roleplay_ws(
    websocket: WebSocket,
    domain:   str = Query(default="General"),
    scenario: str = Query(default="")
):
    await websocket.accept()

    # Auth via JWT cookie
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Fetch resume text for personalised interview questions
    resume_text = None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT resume_text FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        resume_text = row[0]

    loop = asyncio.get_event_loop()
    vad = VADProcessor()

    is_scenario = bool(scenario.strip())
    conversation_history: list = []   # used in scenario mode
    asked_questions:      list = []   # used in interview mode
    current_question:     str  = ""   # used in interview mode

    async def run(fn, *args):
        return await loop.run_in_executor(_executor, fn, *args)

    async def send(data: dict):
        await websocket.send_text(json.dumps(data))

    async def send_question(text: str):
        audio_b64 = await run(text_to_speech, text)
        await send({"type": "question", "text": text, "audio": audio_b64})

    try:
        # ── Opening message ───────────────────────────────────────────────────
        if is_scenario:
            opening = await run(_scenario_opening, scenario)
            conversation_history.append({"role": "assistant", "content": opening})
            await send_question(opening)
        else:
            first_q = await run(generate_question, domain, asked_questions, resume_text)
            asked_questions.append(first_q)
            current_question = first_q
            await send_question(first_q)

        # ── Main loop ─────────────────────────────────────────────────────────
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            # Binary frame — audio chunk from browser MediaRecorder
            if message.get("bytes"):
                vad.add_chunk(message["bytes"])
                continue

            # Text frame — control signal
            if not message.get("text"):
                continue

            try:
                data = json.loads(message["text"])
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "end_of_speech":
                audio = vad.flush()
                if not audio:
                    continue

                try:
                    transcript = await run(
                        speech_to_text, "recording.webm", audio, "audio/webm"
                    )
                except Exception:
                    await send({"type": "error", "message": "Transcription failed"})
                    continue

                if is_scenario:
                    # ── Scenario mode: stay in character, no scoring ──────────
                    conversation_history.append({"role": "user", "content": transcript})
                    try:
                        reply = await run(_scenario_reply, scenario, list(conversation_history))
                    except Exception:
                        await send({"type": "error", "message": "Could not generate reply"})
                        continue
                    conversation_history.append({"role": "assistant", "content": reply})
                    await send_question(reply)

                else:
                    # ── Interview mode: evaluate then next question ───────────
                    try:
                        evaluation = await run(evaluate_answer, current_question, transcript)
                    except Exception:
                        evaluation = {"score": 0, "feedback": "Evaluation failed. Please try again."}

                    await send({
                        "type":       "feedback",
                        "transcript": transcript,
                        "score":      evaluation["score"],
                        "feedback":   evaluation["feedback"]
                    })

                    try:
                        next_q = await run(generate_question, domain, asked_questions, resume_text)
                    except Exception:
                        await send({"type": "error", "message": "Could not generate next question"})
                        continue

                    asked_questions.append(next_q)
                    current_question = next_q
                    await send_question(next_q)

            elif msg_type == "end_session":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await send({"type": "error", "message": str(e)})
        except Exception:
            pass
