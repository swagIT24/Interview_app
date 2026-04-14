from fastapi import APIRouter
from models.schemas import SubmitAnswerRequest
from services.interview_logic import evaluate_answer
from models.schemas import SessionCreate
from services.interview_logic import start_interview
from services.interview_logic import *
from services.auth_service import get_current_user
from fastapi import Depends
from services.interview_logic import *
import json

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message":"interviwe router working"}

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
        
    # 1️⃣ Evaluate answer (updates DB: score, question number, difficulty, completion)
    evaluation = evaluate_answer(data.answer, data.session_id)

    # 2️⃣ Handle error
    if "error" in evaluation:
        return evaluation

    # 3️⃣ If interview completed → no next question
    if evaluation["is_completed"]:
        return {
            **evaluation,
            "next_question": None
        }

    # 4️⃣ Fetch session state from DB
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT domain, difficulty_level, asked_questions
        FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (data.session_id, user_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    domain, difficulty, asked = row

    # 5️⃣ Convert asked_questions from string → list
    asked_questions = json.loads(asked) if asked else []

    # 6️⃣ Get next question (NO repetition)
    question_data = get_next_question(domain, difficulty, asked_questions)

    if not question_data:
        next_question = "No more questions available"
    else:
        # 7️⃣ Save question ID to DB
        update_asked_questions(data.session_id, question_data["id"])
        next_question = question_data["question"]

    # 8️⃣ Return response
    return {
        **evaluation,
        "next_question": next_question
    }

@router.post("/start-session")
def start_session(data: SessionCreate, user_id: int = Depends(get_current_user)):

    # 1️⃣ Create session
    session = start_interview(user_id, data.candidate_name, data.domain)
    session_id = session["session_id"]

    # 2️⃣ Get session details
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT domain, difficulty_level, asked_questions
        FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (session_id, user_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Session not found"}

    domain, difficulty, asked = row
    asked_questions = json.loads(asked) if asked else []

    # 3️⃣ Generate FIRST question
    question_data = get_next_question(domain, difficulty, asked_questions)

    if question_data:
        first_question = question_data["question"]   # ✅ DEFINE FIRST

        update_asked_questions(session_id, question_data["id"])

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO interview_answers (session_id, question, answer, score, feedback, time_taken)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, first_question, "", 0, "", 0))

        conn.commit()
        conn.close()
        
        first_question = question_data["question"]
    else:
        first_question = "No questions available"

    # 4️⃣ Return response
    return {
        "session_id": session_id,
        "current_question": first_question,
        "current_question_number": 1,
        "difficulty_level": difficulty
    }


@router.get("/session/{session_id}")
def get_session(session_id: int, user_id: int = Depends(get_current_user)):
    return fetch_session(session_id, user_id)