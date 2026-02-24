from database.connections import create_session
from database.connections import insert_answer
from database.connections import *


SIMILARITY_THRESHOLD = 0.85
MAX_QUESTIONS = 10
ADAPTIVE_WINDOW = 3

# def evaluate_answer(answer: str, session_id: int):
#     score = len(answer)//10

#     feedback = "Good effort. Expand more with examples" if score<5 else "exellent answer"

#     return{
#         "score":score,
#         "feedback":feedback,
#         "session_id":session_id
#     }

def start_interview(user_id: int, candidate_name: str, domain: str):
    session_id = create_session(user_id, candidate_name, domain)
    return {
        "session_id": session_id,
        "message": "Interview session started"
    }

def evaluate_answer(answer: str, session_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT current_question_number, max_questions, difficulty_level, is_completed
            FROM interview_sessions
            WHERE id = ?
        """, (session_id,))
        
        session = cursor.fetchone()

        if not session:
            return {"error": "Session not found"}

        current_q, max_q, difficulty, is_completed = session
        if is_completed:
            return {"error": "Interview already completed"}
        score = len(answer) // 10
        feedback = (
            "Excellent answer"
            if score > 10
            else "Improve structure and add examples"
        )

        question_text = f"Question {current_q}"
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

        # 5️⃣ Atomic increment question number
        cursor.execute("""
            UPDATE interview_sessions
            SET current_question_number = current_question_number + 1
            WHERE id = ?
        """, (session_id,))

        # 6️⃣ Fetch updated question number
        cursor.execute("""
            SELECT current_question_number
            FROM interview_sessions
            WHERE id = ?
        """, (session_id,))
        
        new_q = cursor.fetchone()[0]

        # 7️⃣ Mark session completed if needed
        if new_q > max_q:
            cursor.execute("""
                UPDATE interview_sessions
                SET is_completed = 1
                WHERE id = ?
            """, (session_id,))
            is_completed = 1

        scores = get_last_n_scores(cursor, session_id, ADAPTIVE_WINDOW)


        if len(scores) == ADAPTIVE_WINDOW:
            avg_score = sum(scores) / len(scores)

            levels = ["easy", "medium", "hard"]
            index = levels.index(difficulty)

            if avg_score > 12 and index < len(levels) - 1:
                difficulty = levels[index + 1]
            elif avg_score < 6 and index > 0:
                difficulty = levels[index - 1]

            cursor.execute("""
                UPDATE interview_sessions
                SET difficulty_level = ?
                WHERE id = ?
            """, (difficulty, session_id))

        # 🔟 Commit entire transaction
        conn.commit()

        return {
            "score": score,
            "feedback": feedback,
            "current_question_number": new_q,
            "difficulty_level": difficulty,
            "is_completed": bool(is_completed)
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()

def fetch_session(session_id: int, user_id: int):
    result = get_session_with_answer(session_id,user_id)

    if not result:
        return {"error":"session not found"}
    return result

def adjust_diff(curr_diff, avg_score):
    lvl = ['easy','hard','medium']
    index = lvl.index(curr_diff)

    if avg_score > 12 and index < len(lvl) -1:
        index +=1

    elif avg_score < 6 and index > 0:
        index -=1

    return lvl[index]


def generate_next_question(session_id: int):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT current_question_number, difficulty_level, domain, is_completed
        FROM interview_sessions
        WHERE id = ?
    """, (session_id,))

    session = cursor.fetchone()
    conn.close()

    if not session:
        return {"error": "Session not found"}

    current_q, difficulty, domain, is_completed = session

    if is_completed:
        return None

    question = f"{difficulty.capitalize()} question {current_q} in {domain}"

    return question
