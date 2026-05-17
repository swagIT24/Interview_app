from fastapi import APIRouter
from models.schemas import SubmitAnswerRequest
from services.interview_logic import process_answer
from models.schemas import SessionCreate
from services.interview_logic import start_interview
from services.interview_logic import *
from services.auth_service import get_current_user
from fastapi import Depends
from services.interview_logic import *
import json
from services.tts_service import text_to_speech
from fastapi import Body
from concurrent.futures import ThreadPoolExecutor
from fastapi.responses import StreamingResponse

from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message":"interviwe router working"}

@router.post("/tts")
def tts(data: TTSRequest):
    audio_b64 = text_to_speech(data.text)
    return {"audio": audio_b64}

@router.post("/submit-answer")
def submit_answer(data: SubmitAnswerRequest, user_id: int = Depends(get_current_user)):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT is_completed
        FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (data.session_id, user_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    if row[0] == 1:
        return {
            "message": "Interview already completed",
            "is_completed": True
        }

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT domain, asked_questions
        FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (data.session_id, user_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    domain, asked = row
    asked_questions = json.loads(asked) if asked else []

    # ← CHANGED: run all 3 in parallel
    with ThreadPoolExecutor() as executor:

        eval_future = executor.submit(
            process_answer, data.answer, data.session_id, data.question_text
        )
        question_future = executor.submit(
            get_next_question, domain, asked_questions, user_id
        )

        # get question first so we can start TTS immediately
        question_data = question_future.result()

        if question_data:
            next_question = question_data["question"]["question"]
            # ← NEW: start TTS while evaluation is still running
            tts_future = executor.submit(text_to_speech, next_question)
        
        # wait for evaluation
        evaluation = eval_future.result()

        if "error" in evaluation:
            return evaluation

        if not question_data:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE interview_sessions
                SET is_completed = 1
                WHERE id = ? AND user_id = ?
            """, (data.session_id, user_id))
            conn.commit()
            conn.close()

            return {
                **evaluation,
                "next_question": None,
                "audio": None,
                "is_completed": True
            }

        # ← get TTS result (likely already done by now)
        try:
            audio_b64 = tts_future.result()
            print("TTS SUCCESS, length:", len(audio_b64))
        except Exception as e:
            print("TTS FAILED:", e)
            audio_b64 = None

    update_asked_questions(data.session_id, next_question)

    return {
        **evaluation,
        "next_question": next_question,
        "audio": audio_b64,
        "is_completed": False
    }


@router.post("/start-session")
def start_session(data: SessionCreate, user_id: int = Depends(get_current_user)):

    session = start_interview(user_id, data.candidate_name, data.domain)
    session_id = session["session_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT domain, asked_questions
        FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (session_id, user_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    domain, asked = row
    asked_questions = json.loads(asked) if asked else []

    question_data = get_next_question(domain, asked_questions,user_id)

    if question_data:
        first_question = question_data["question"]["question"]
        question_id = question_data["question"]["id"]

        update_asked_questions(session_id, question_id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interview_answers (session_id, question, answer, score, feedback, time_taken)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, first_question, "", 0, "", 0))
        conn.commit()
        conn.close()

    else:
        first_question = "No questions available"

    audio_b64 = text_to_speech(first_question)

    return {
        "session_id": session_id,
        "current_question": first_question,
        "current_question_number": 1,
        "audio": audio_b64
    }


@router.get("/session/{session_id}")
def get_session(session_id: int, user_id: int = Depends(get_current_user)):
    return fetch_session(session_id, user_id)


@router.post("/submit-answer-stream")  # ← NEW route
async def submit_answer_stream(data: SubmitAnswerRequest, user_id: int = Depends(get_current_user)):

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT is_completed FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (data.session_id, user_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    if row[0] == 1:
        return {"message": "Interview already completed", "is_completed": True}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT domain, asked_questions FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (data.session_id, user_id))
    row = cursor.fetchone()
    conn.close()

    domain, asked = row
    asked_questions = json.loads(asked) if asked else []

    def generate():
        # Run evaluation and question generation in parallel
        with ThreadPoolExecutor() as executor:
            eval_future = executor.submit(
                process_answer, data.answer, data.session_id, data.question_text
            )
            question_future = executor.submit(
                get_next_question, domain, asked_questions
            )
            evaluation = eval_future.result()
            question_data = question_future.result()

        # Stream score first — instant feedback
        yield f"SCORE:{evaluation['score']}\n"

        # Stream feedback word by word
        yield f"FEEDBACK:{evaluation['feedback']}\n"

        # After feedback, send next question and audio
        if question_data:
            next_question = question_data["question"]["question"]
            update_asked_questions(data.session_id, next_question)

            try:
                audio_b64 = text_to_speech(next_question)
            except:
                audio_b64 = None

            yield f"\nNEXT_QUESTION:{next_question}\n"
            yield f"AUDIO:{audio_b64}\n"
        else:
            yield f"\nCOMPLETED:true\n"

    return StreamingResponse(generate(), media_type="text/plain")