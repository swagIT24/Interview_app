import asyncio
import json
import re
import time
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

_FEMALE_KEYWORDS = {
    "girlfriend", "girl", "woman", "female", "mother", "mom", "wife",
    "sister", "aunt", "daughter", "lady", "boss lady", "female boss",
    "female interviewer", "female recruiter", "recruiter", "nurse",
    "teacher", "she", "her",
}
_MALE_KEYWORDS = {
    "boyfriend", "guy", "man", "male", "father", "dad", "husband",
    "brother", "uncle", "son", "boss", "male boss", "male interviewer",
    "male recruiter", "he", "him",
}


def _detect_voice(scenario: str) -> str:
    lower = scenario.lower()
    tokens = set(lower.replace(",", " ").replace(".", " ").split())
    female_hits = tokens & _FEMALE_KEYWORDS
    male_hits   = tokens & _MALE_KEYWORDS
    if female_hits and not male_hits:
        return "nova"
    if male_hits and not female_hits:
        return "onyx"
    return "alloy"


def _generate_character(scenario: str) -> str:
    """Use GPT to build a vivid, specific character for the scenario."""
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"The user wants to practice this real-life conversation: \"{scenario}\"\n\n"
                "Create a vivid, specific character for the OTHER person in this scenario "
                "(not the user — the person the user will be speaking with).\n\n"
                "Include: a name, age, job or relationship to the user, specific personality "
                "traits, current mood or emotional state, and what's happening right now "
                "(the exact situation as it starts).\n\n"
                "Make it feel real — not generic. Specific details make it believable.\n\n"
                "Write it as a 2–3 paragraph character brief for an actor. "
                "End with a single line: 'Just be [name]. React naturally, as they would.'\n\n"
                "Return only the character brief, nothing else."
            )
        }],
        temperature=0.9,
        max_tokens=280,
    )
    return resp.choices[0].message.content.strip()


def _scenario_opening(character: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": character},
            {"role": "user",   "content": (
                "The conversation is starting right now. "
                "Deliver your opening line — speak directly to the person in front of you. "
                "One or two sentences, nothing else. No stage directions."
            )}
        ],
        temperature=0.9,
        max_tokens=80,
    )
    return resp.choices[0].message.content.strip()


# ── Streaming reply helpers ───────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r'[.?!]\s+')


async def _stream_roleplay_sentences(character: str, history: list, loop):
    """
    Async generator. Streams GPT tokens from a background thread into an
    asyncio.Queue, then yields complete sentences as they arrive.
    Sentence boundary = terminal punctuation followed by whitespace (or flush on end).
    """
    token_q: asyncio.Queue = asyncio.Queue()

    def _produce():
        try:
            stream = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": character}] + history,
                temperature=0.9,
                max_tokens=120,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    loop.call_soon_threadsafe(token_q.put_nowait, delta.content)
        finally:
            loop.call_soon_threadsafe(token_q.put_nowait, None)

    produce_future = loop.run_in_executor(_executor, _produce)

    buf = ""
    while True:
        token = await token_q.get()
        if token is None:
            if buf.strip():
                yield buf.strip()
            break
        buf += token
        # Emit complete sentences: punctuation followed by whitespace
        while True:
            m = _SENTENCE_RE.search(buf)
            if not m:
                break
            sentence = buf[:m.end()].strip()
            buf = buf[m.end():]
            if len(sentence) > 4:
                yield sentence

    await produce_future


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
    voice = _detect_voice(scenario) if is_scenario else "alloy"
    character:            str  = ""   # GPT-generated character brief, set before opening
    conversation_history: list = []   # used in scenario mode
    asked_questions:      list = []   # used in interview mode
    current_question:     str  = ""   # used in interview mode

    async def run(fn, *args):
        return await loop.run_in_executor(_executor, fn, *args)

    async def send(data: dict):
        await websocket.send_text(json.dumps(data))

    async def send_question(text: str):
        audio_b64 = await run(text_to_speech, text, voice)
        await send({"type": "question", "text": text, "audio": audio_b64})

    async def process_speech(audio_wav: bytes):
        """Handle a completed speech turn (roleplay or interview mode)."""
        nonlocal current_question
        if is_scenario:
            # ── Roleplay: Whisper → streaming GPT → per-sentence TTS ─────────
            t0 = time.time()
            print(f"[ROLEPLAY TIMING] Whisper start: {time.time()-t0:.2f}s")
            try:
                transcript = await run(
                    speech_to_text, "recording.wav", audio_wav, "audio/wav"
                )
            except Exception:
                await send({"type": "error", "message": "Transcription failed"})
                return
            print(f"[ROLEPLAY TIMING] Whisper end: {time.time()-t0:.2f}s")

            conversation_history.append({"role": "user", "content": transcript})

            # Stream GPT → sentence-split → TTS each sentence immediately.
            # While TTS[n] runs in the executor, GPT streams sentence[n+1] in its thread.
            reply_parts: list = []
            first_chunk = True
            print(f"[ROLEPLAY TIMING] GPT stream start: {time.time()-t0:.2f}s")
            try:
                async for sentence in _stream_roleplay_sentences(
                    character, list(conversation_history), loop
                ):
                    reply_parts.append(sentence)
                    tts_t = time.time()
                    audio_b64 = await run(text_to_speech, sentence, voice)
                    print(f"[ROLEPLAY TIMING] TTS chunk {'(first) ' if first_chunk else ''}"
                          f"'{sentence[:30]}': {time.time()-tts_t:.2f}s | total: {time.time()-t0:.2f}s")
                    await send({"type": "audio_chunk", "audio": audio_b64, "text": sentence})
                    if first_chunk:
                        print(f"[ROLEPLAY TIMING] first audio sent to browser: {time.time()-t0:.2f}s")
                        first_chunk = False
            except Exception as e:
                await send({"type": "error", "message": "Reply generation failed"})
                return

            full_reply = " ".join(reply_parts)
            conversation_history.append({"role": "assistant", "content": full_reply})
            # Empty audio signals all chunks sent; browser updates text display
            await send({"type": "question", "text": full_reply, "audio": ""})
            print(f"[ROLEPLAY TIMING] turn complete: {time.time()-t0:.2f}s")

        else:
            # ── Interview: generate next question immediately, then transcribe +
            #    evaluate in parallel ──────────────────────────────────────────
            t0 = time.time()
            gen_task = loop.run_in_executor(
                _executor, generate_question, domain, asked_questions, resume_text
            )

            print(f"[ROLEPLAY TIMING] Whisper start: {time.time()-t0:.2f}s")
            try:
                transcript = await run(
                    speech_to_text, "recording.wav", audio_wav, "audio/wav"
                )
            except Exception:
                gen_task.cancel()
                await send({"type": "error", "message": "Transcription failed"})
                return
            print(f"[ROLEPLAY TIMING] Whisper end: {time.time()-t0:.2f}s")

            print(f"[ROLEPLAY TIMING] GPT start (eval+gen parallel): {time.time()-t0:.2f}s")
            eval_task = loop.run_in_executor(
                _executor, evaluate_answer, current_question, transcript
            )

            try:
                evaluation, next_q = await asyncio.gather(eval_task, gen_task)
            except Exception:
                evaluation = {"score": 0, "feedback": "Evaluation failed. Please try again."}
                try:
                    next_q = await gen_task
                except Exception:
                    await send({"type": "error", "message": "Could not generate next question"})
                    return
            print(f"[ROLEPLAY TIMING] GPT end (eval+gen parallel): {time.time()-t0:.2f}s")

            print(f"[ROLEPLAY TIMING] TTS start: {time.time()-t0:.2f}s")
            tts_task = loop.run_in_executor(_executor, text_to_speech, next_q, voice)

            await send({
                "type":       "feedback",
                "transcript": transcript,
                "score":      evaluation["score"],
                "feedback":   evaluation["feedback"]
            })

            try:
                audio_b64 = await tts_task
            except Exception:
                audio_b64 = ""
            print(f"[ROLEPLAY TIMING] TTS end: {time.time()-t0:.2f}s")

            asked_questions.append(next_q)
            current_question = next_q
            await send({"type": "question", "text": next_q, "audio": audio_b64})
            print(f"[ROLEPLAY TIMING] audio sent to browser: {time.time()-t0:.2f}s")

    try:
        # ── Opening message ───────────────────────────────────────────────────
        if is_scenario:
            character = await run(_generate_character, scenario)
            print(f"[roleplay] character brief:\n{character}\n")
            opening = await run(_scenario_opening, character)
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

            # Binary frame — raw Int16 LE PCM from browser AudioWorklet
            raw = message.get("bytes")
            if raw:
                speech_ended = await loop.run_in_executor(_executor, vad.add_bytes, raw)
                if speech_ended:
                    audio_wav = vad.flush()
                    if audio_wav:
                        print(f"[ROLEPLAY TIMING] VAD triggered (speech end): {time.time():.3f}")
                        await send({"type": "processing"})
                        await process_speech(audio_wav)
                continue

            # Text frame — control signal
            if not message.get("text"):
                continue

            try:
                data = json.loads(message["text"])
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "stream_start":
                sr = int(data.get("sample_rate", 44100))
                vad.set_sample_rate(sr)
                print(f"[vad] stream_start sample_rate={sr}")

            elif msg_type == "end_session":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await send({"type": "error", "message": str(e)})
        except Exception:
            pass
