from fastapi import APIRouter, Request
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
from services.limiter import limiter

from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message":"interviwe router working"}

@router.post("/tts")
def tts(data: TTSRequest, user_id: int = Depends(get_current_user)):
    audio_b64 = text_to_speech(data.text)
    return {"audio": audio_b64}

@router.post("/submit-answer")
@limiter.limit("20/minute")
def submit_answer(request: Request, data: SubmitAnswerRequest, user_id: int = Depends(get_current_user)):

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT domain, asked_questions
        FROM interview_sessions
        WHERE id = %s AND user_id = %s
    """, (data.session_id, user_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    domain, asked = row
    asked_questions = json.loads(asked) if asked else []

    # Re-submission check: question already answered → update row, no increment, still return next question
    # NOTE: must require a non-empty answer — /start-session no longer inserts an empty
    # placeholder row, but this guard also protects against any other future code path
    # that might create a question row before the user actually answers it.
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM interview_answers
        WHERE session_id = %s AND question = %s AND answer != ''
        LIMIT 1
    """, (data.session_id, data.question_text))
    is_resubmit = cursor.fetchone() is not None
    conn.close()

    # Check practice limit before anything else
    conn2 = get_connection()
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT practice_count FROM users WHERE id = %s", (user_id,))
    user_row = cursor2.fetchone()
    conn2.close()
    if user_row and user_row["practice_count"] >= 5:
        return {"error": "limit_reached", "message": "You have used your 5 free practice answers. Upgrade to continue."}

    if is_resubmit:
        with ThreadPoolExecutor() as executor:
            eval_future = executor.submit(
                process_answer, data.answer, data.session_id, data.question_text, user_id, True
            )
            question_future = executor.submit(
                get_next_question, domain, asked_questions, user_id
            )

            question_data = question_future.result()
            print(f"DEBUG question_data: {question_data}")
            if question_data:
                next_question = question_data["question"]["question"]
                tts_future = executor.submit(text_to_speech, next_question)

            evaluation = eval_future.result()

        if "error" in evaluation:
            return evaluation

        audio_b64 = None
        next_q = None
        if question_data:
            next_q = next_question
            try:
                audio_b64 = tts_future.result()
            except Exception:
                audio_b64 = None

        return {
            "score":               evaluation.get("score"),
            "feedback":            evaluation.get("feedback"),
            "score_breakdown":     evaluation.get("score_breakdown"),
            "strongest_dimension": evaluation.get("strongest_dimension"),
            "weakest_dimension":   evaluation.get("weakest_dimension"),
            "one_line_verdict":    evaluation.get("one_line_verdict"),
            "missed_key_point":    evaluation.get("missed_key_point"),
            "good_answer_example":  evaluation.get("good_answer_example"),
            "next_question": next_q,
            "audio": audio_b64,
            "is_completed": False,
        }

    # ← CHANGED: run all 3 in parallel
    with ThreadPoolExecutor() as executor:

        eval_future = executor.submit(
            process_answer, data.answer, data.session_id, data.question_text, user_id
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

        if evaluation.get("is_completed") or not question_data:
            if not evaluation.get("is_completed"):
                # fallback: process_answer didn't catch it, mark complete now
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE interview_sessions
                    SET is_completed = 1
                    WHERE id = %s AND user_id = %s
                """, (data.session_id, user_id))
                conn.commit()
                conn.close()

            return {
                "score":               evaluation.get("score"),
                "feedback":            evaluation.get("feedback"),
                "score_breakdown":     evaluation.get("score_breakdown"),
                "strongest_dimension": evaluation.get("strongest_dimension"),
                "weakest_dimension":   evaluation.get("weakest_dimension"),
                "one_line_verdict":    evaluation.get("one_line_verdict"),
                "missed_key_point":    evaluation.get("missed_key_point"),
                "good_answer_example":  evaluation.get("good_answer_example"),
                "next_question": None,
                "audio": None,
                "is_completed": True,
            }

        # ← get TTS result (likely already done by now)
        try:
            audio_b64 = tts_future.result()
            print("TTS SUCCESS, length:", len(audio_b64))
        except Exception as e:
            print("TTS FAILED:", e)
            audio_b64 = None

    update_asked_questions(data.session_id, next_question, user_id)

    return {
        "score":               evaluation.get("score"),
        "feedback":            evaluation.get("feedback"),
        "score_breakdown":     evaluation.get("score_breakdown"),
        "strongest_dimension": evaluation.get("strongest_dimension"),
        "weakest_dimension":   evaluation.get("weakest_dimension"),
        "one_line_verdict":    evaluation.get("one_line_verdict"),
        "missed_key_point":    evaluation.get("missed_key_point"),
        "good_answer_example": evaluation.get("good_answer_example"),
        "next_question": next_question,
        "audio": audio_b64,
        "is_completed": False,
    }


@router.post("/start-session")
@limiter.limit("10/minute")
def start_session(request: Request, data: SessionCreate, user_id: int = Depends(get_current_user)):

    session = start_interview(user_id, data.candidate_name, data.domain)
    session_id = session["session_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT domain, asked_questions
        FROM interview_sessions
        WHERE id = %s AND user_id = %s
    """, (session_id, user_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    domain, asked = row
    asked_questions = json.loads(asked) if asked else []
    print("use_resume:", data.use_resume)
    question_data = get_next_question(domain, asked_questions, user_id if data.use_resume else None)

    if question_data:
        first_question = question_data["question"]["question"]
        question_id = question_data["question"]["id"]

        update_asked_questions(session_id, question_id, user_id)
        # NOTE: no placeholder row is inserted into interview_answers here anymore.
        # The real row is created by process_answer()/insert_answer() once the user
        # actually submits an answer. Pre-inserting an empty-answer row used to make
        # /submit-answer misclassify the user's first real answer as a "resubmit"
        # (see is_resubmit check above), which skipped current_question_number
        # bookkeeping and returned a differently-shaped response for question 1.

    else:
        first_question = "No questions available"

    audio_b64 = text_to_speech(first_question)

    return {
        "session_id": session_id,
        "current_question": first_question,
        "current_question_number": 1,
        "audio": audio_b64
    }


@router.get("/sessions")
def get_sessions(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            s.id,
            s.domain,
            s.created_at,
            s.is_completed,
            s.current_question_number,
            ROUND(AVG(NULLIF(a.score, 0)), 1) AS avg_score,
            COUNT(CASE WHEN a.answer != '' THEN 1 END) AS question_count
        FROM interview_sessions s
        LEFT JOIN interview_answers a ON a.session_id = s.id
        WHERE s.user_id = %s
        GROUP BY s.id
        ORDER BY s.created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@router.get("/session/{session_id}")
def get_session(session_id: int, user_id: int = Depends(get_current_user)):
    return fetch_session(session_id, user_id)


@router.post("/submit-answer-stream")  # ← NEW route
async def submit_answer_stream(data: SubmitAnswerRequest, user_id: int = Depends(get_current_user)):

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT is_completed FROM interview_sessions
        WHERE id = %s AND user_id = %s
    """, (data.session_id, user_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    if row[0] == 1:
        return {"message": "Interview already completed", "is_completed": True}

    # Check practice limit (BUG-011 fix)
    conn2 = get_connection()
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT practice_count FROM users WHERE id = %s", (user_id,))
    user_row = cursor2.fetchone()
    conn2.close()
    if user_row and user_row["practice_count"] >= 5:
        return {"error": "limit_reached", "message": "You have used your 5 free practice answers. Upgrade to continue."}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT domain, asked_questions FROM interview_sessions
        WHERE id = %s AND user_id = %s
    """, (data.session_id, user_id))
    row = cursor.fetchone()
    conn.close()

    domain, asked = row
    asked_questions = json.loads(asked) if asked else []

    def generate():
        # Run evaluation and question generation in parallel
        with ThreadPoolExecutor() as executor:
            eval_future = executor.submit(
                process_answer, data.answer, data.session_id, data.question_text, user_id
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
            update_asked_questions(data.session_id, next_question, user_id)

            try:
                audio_b64 = text_to_speech(next_question)
            except:
                audio_b64 = None

            yield f"\nNEXT_QUESTION:{next_question}\n"
            yield f"AUDIO:{audio_b64}\n"
        else:
            yield f"\nCOMPLETED:true\n"

    return StreamingResponse(generate(), media_type="text/plain")