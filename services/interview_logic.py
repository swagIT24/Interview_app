from database.connections import create_session
from database.connections import insert_answer
from database.connections import *
from services.questions import *
import random
import json
from services.evaluation_service import evaluate_answer
from services.question_generation_service import generate_question
from services.tts_service import text_to_speech

ADAPTIVE_WINDOW = 3


def start_interview(user_id: int, candidate_name: str, domain: str):
    session_id = create_session(user_id, candidate_name, domain)

    return {
        "session_id": session_id,
        "message": "Interview session started",
        "asked_questions": []
    }


def process_answer(answer: str, session_id: int, question_text: str):

    if not answer or answer.strip() == "":
        return {
            "score": 0,
            "feedback": "Please provide an answer before submitting.",
            "is_completed": False,
            "current_question_number": None,
            "difficulty_level": None
        }

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT current_question_number, is_completed
            FROM interview_sessions
            WHERE id = ?
        """, (session_id,))

        session = cursor.fetchone()

        if not session:
            return {"error": "Session not found"}

        current_q, is_completed = session

        if is_completed:
            return {"error": "Interview already completed"}

        # Evaluate via LLM using question passed directly
        try:
            result = evaluate_answer(question_text, answer)
            score, feedback = result["score"], result["feedback"]
        except Exception as e:
            print("LLM failed:", e)
            score = len(answer) // 10
            feedback = "Fallback evaluation"

        # Save answer with correct question_text
        time_taken = 30
        insert_answer(
            cursor,
            session_id,
            question_text,
            answer,
            score,
            feedback,
            time_taken
        )

        # Increment question number
        cursor.execute("""
            UPDATE interview_sessions
            SET current_question_number = current_question_number + 1
            WHERE id = ?
        """, (session_id,))

        cursor.execute("""
            SELECT current_question_number
            FROM interview_sessions
            WHERE id = ?
        """, (session_id,))

        new_q = cursor.fetchone()[0]

        # Adaptive difficulty every 3 answers
        scores = get_last_n_scores(cursor, session_id, ADAPTIVE_WINDOW)

        # if len(scores) == ADAPTIVE_WINDOW:
        #     avg_score = sum(scores) / len(scores)
        #     levels = ["easy", "medium", "hard"]
        #     index = levels.index(difficulty)

        #     if avg_score > 12 and index < len(levels) - 1:
        #         difficulty = levels[index + 1]
        #     elif avg_score < 6 and index > 0:
        #         difficulty = levels[index - 1]

        #     cursor.execute("""
        #         UPDATE interview_sessions
        #         SET difficulty_level = ?
        #         WHERE id = ?
        #     """, (difficulty, session_id))

        # conn.commit()

        return {
            "score": score,
            "feedback": feedback,
            "current_question_number": new_q,
            "is_completed": False
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()


def fetch_session(session_id: int, user_id: int):

    result = get_session_with_answer(session_id, user_id)

    if not result:
        return {"error": "session not found"}

    session = result["session"]
    answers = result["answers"]

    return {
        "session_id": session_id,
        "domain": session["domain"],
        "difficulty_level": session["difficulty_level"],
        "current_question_number": session["current_question_number"],
        "is_completed": bool(session["is_completed"]),
        "current_question": answers[-1]["question"] if answers else None
    }


# def get_next_question(domain, difficulty, asked_questions):

#     difficulty = difficulty.lower()

#     domain_map = {
#         "ML": "Machine Learning",
#         "Machine Learning": "Machine Learning",
#         "Python": "Python",
#         "Java": "Java",
#         "Statistics": "Statistics"
#     }

#     domain = domain_map.get(domain, domain)

#     level_order = ["easy", "medium", "hard"]
#     current_index = level_order.index(difficulty)

#     for level in level_order[current_index:]:
#         questions = QUESTION_BANK.get(domain, {}).get(level, [])
#         remaining = [q for q in questions if q["id"] not in asked_questions]

#         if remaining:
#             return {
#                 "question": random.choice(remaining),
#                 "actual_difficulty": level
#             }

#     return None


def get_next_question(domain, asked_questions, user_id=None):  # ← add user_id

    # ← fetch resume text if user_id provided
    resume_text = None
    if user_id:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT resume_text FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            resume_text = row[0]

    question_text = generate_question(domain, asked_questions=asked_questions, resume_text=resume_text)

    return {
        "question": {
            "id": question_text,
            "question": question_text,
            "topic": domain
        }
    }


def update_asked_questions(session_id, question_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asked_questions FROM interview_sessions
        WHERE id = ?
    """, (session_id,))

    row = cursor.fetchone()
    asked = json.loads(row[0]) if row and row[0] else []
    asked.append(question_id)

    cursor.execute("""
        UPDATE interview_sessions
        SET asked_questions = ?
        WHERE id = ?
    """, (json.dumps(asked), session_id))

    conn.commit()
    conn.close()