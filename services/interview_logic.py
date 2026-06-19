import asyncio
import json
import logging
from database.connections import create_session, insert_answer, get_connection, get_session_with_answer, get_last_n_scores
from services.evaluation_service import evaluate_answer, generate_feedback
from services.question_generation_service import generate_question

logger = logging.getLogger(__name__)

ADAPTIVE_WINDOW = 5


def start_interview(user_id: int, candidate_name: str, domain: str):
    session_id = create_session(user_id, candidate_name, domain)
    return {
        "session_id": session_id,
        "message": "Interview session started",
        "asked_questions": [],
    }


def _difficulty_from_scores(scores: list) -> str:
    if not scores:
        return "intermediate"
    avg = sum(scores) / len(scores)
    if avg >= 7.5:
        return "advanced"
    if avg <= 4.5:
        return "beginner"
    return "intermediate"


def process_answer(answer: str, session_id: int, question_text: str, user_id:int = None, is_resubmit: bool = False):
    if not answer or answer.strip() == "":
        return {
            "score": 0,
            "feedback": "Please provide an answer before submitting.",
            "is_completed": False,
            "current_question_number": None,
        }

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT current_question_number, is_completed
            FROM interview_sessions WHERE id = %s
        """, (session_id,))
        session = cursor.fetchone()

        if not session:
            return {"error": "Session not found"}

        current_q, is_completed = session["current_question_number"], session["is_completed"]

        if is_completed:
            return {"error": "Interview already completed"}

        is_admin = False
        if user_id:
            cursor.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
            user_row = cursor.fetchone()
            is_admin = bool(user_row["is_admin"]) if user_row else False

        # Adaptive difficulty from recent history
        recent_scores = get_last_n_scores(cursor, session_id, ADAPTIVE_WINDOW)
        difficulty = _difficulty_from_scores(recent_scores)

        # 1+2. Run chain-of-thought evaluation then feedback in one event loop.
        # process_answer runs in a ThreadPoolExecutor thread (no running loop),
        # so asyncio.run() is safe here.
        async def _evaluate_and_feedback():
            sr = await evaluate_answer(question_text, answer, difficulty)
            fb = await generate_feedback(
                question_text, answer, sr, difficulty,
                sr.get("analysis_text", ""),
            )
            return sr, fb

        try:
            score_result, feedback = asyncio.run(_evaluate_and_feedback())
        except Exception as e:
            logger.error(f"evaluation pipeline failed: {e}")
            score_result = {
                "scores": {}, "total": 5,
                "strongest_dimension": "clarity", "weakest_dimension": "depth",
                "one_line_verdict": "Could not evaluate.", "missed_key_point": None,
                "good_answer_example": "", "analysis_text": "",
            }
            feedback = f"Score: 5/10. Focus on {score_result.get('weakest_dimension', 'depth')}."

        # 3. Persist
        if is_resubmit:
            cursor.execute("""
                UPDATE interview_answers
                SET answer = %s, score = %s, feedback = %s
                WHERE session_id = %s AND question = %s
            """, (answer, score_result["total"], feedback, session_id, question_text))
            if user_id and not is_admin:  # ADD THIS
                cursor.execute("UPDATE users SET practice_count = practice_count + 1 WHERE id = %s", (user_id,))
    
            conn.commit()
            return {
                "score":               score_result["total"],
                "feedback":            feedback,
                "score_breakdown":     score_result.get("scores"),
                "strongest_dimension": score_result.get("strongest_dimension"),
                "weakest_dimension":   score_result.get("weakest_dimension"),
                "one_line_verdict":    score_result.get("one_line_verdict"),
                "missed_key_point":    score_result.get("missed_key_point"),
                "good_answer_example":  score_result.get("good_answer_example"),
                "current_question_number": current_q,
                "is_completed": False,
            }

        insert_answer(
            cursor,
            session_id,
            question_text,
            answer,
            score_result["total"],
            feedback,
            time_taken=30,
            score_breakdown=score_result.get("scores"),
            weakest_dimension=score_result.get("weakest_dimension"),
            model_answer_hint=score_result.get("good_answer_example"),
            analysis_text=score_result.get("analysis_text"),
        )

        cursor.execute("""
            UPDATE interview_sessions
            SET current_question_number = current_question_number + 1
            WHERE id = %s
        """, (session_id,))
        conn.commit()

        cursor.execute("""
            SELECT current_question_number, max_questions FROM interview_sessions WHERE id = %s
        """, (session_id,))
        row = cursor.fetchone()
        new_q, max_q = row[0], row[1]
        now_complete = new_q >= max_q
        if now_complete:
            cursor.execute("""
                UPDATE interview_sessions SET is_completed = 1 WHERE id = %s
            """, (session_id,))

        if user_id and not is_admin:
            cursor.execute("""
                UPDATE users SET practice_count = practice_count + 1 WHERE id = %s
            """, (user_id,))

        conn.commit()

        return {
            "score":               score_result["total"],
            "feedback":            feedback,
            "score_breakdown":     score_result.get("scores"),
            "strongest_dimension": score_result.get("strongest_dimension"),
            "weakest_dimension":   score_result.get("weakest_dimension"),
            "one_line_verdict":    score_result.get("one_line_verdict"),
            "missed_key_point":    score_result.get("missed_key_point"),
            "good_answer_example":  score_result.get("good_answer_example"),
            "current_question_number": new_q,
            "is_completed": now_complete,
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
        "session_id":              session_id,
        "domain":                  session["domain"],
        "current_question_number": session["current_question_number"],
        "is_completed":            bool(session["is_completed"]),
        "current_question":        answers[-1]["question"] if answers else None,
    }


def get_next_question(domain, asked_questions, user_id=None):
    """Fetch resume text, compute difficulty from history, delegate to generate_question."""
    resume_text = None
    recent_scores = []

    if user_id:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT resume_text FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            resume_text = row[0]

        # Pull recent scores for adaptive difficulty
        recent_scores = get_last_n_scores(cursor, _get_active_session_id(cursor, user_id), ADAPTIVE_WINDOW)
        conn.close()

    result = generate_question(
        domain=domain,
        asked_questions=asked_questions,
        resume_text=resume_text,
        session_history=recent_scores,
    )

    question_text = result["question"] if isinstance(result, dict) else result

    return {
        "question": {
            "id":         question_text,
            "question":   question_text,
            "topic":      domain,
            "difficulty": result.get("difficulty", "intermediate") if isinstance(result, dict) else "intermediate",
        }
    }


def _get_active_session_id(cursor, user_id: int):
    """Return the most recent session id for a user, or 0 if none."""
    cursor.execute("""
        SELECT id FROM interview_sessions
        WHERE user_id = %s
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0


def update_asked_questions(session_id, question_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asked_questions FROM interview_sessions WHERE id = %s AND user_id = %s
    """, (session_id, user_id))
    row = cursor.fetchone()
    asked = json.loads(row[0]) if row and row[0] else []
    asked.append(question_id)

    cursor.execute("""
        UPDATE interview_sessions SET asked_questions = %s WHERE id = %s AND user_id = %s
    """, (json.dumps(asked), session_id, user_id))

    conn.commit()
    conn.close()
