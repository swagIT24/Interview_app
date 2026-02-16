from database.connections import create_session
from database.connections import insert_answer
from database.connections import *


SIMILARITY_THRESHOLD = 0.85

def evaluate_answer(answer: str, session_id: int):
    score = len(answer)//10

    feedback = "Good effort. Expand more with examples" if score<5 else "exellent answer"

    return{
        "score":score,
        "feedback":feedback,
        "session_id":session_id
    }

def start_interview(candidate_name:str, domain:str):
    session_id = create_session(candidate_name,domain)
    return {
        "session_id": session_id,
        "message": "Interview session started"
    }

def evaluate_answer(answer: str, session_id: int):
    score = len(answer) // 10
    
    feedback = "Excellent answer" if score > 10 else "Improve structure and examples"

    question = "Dummy question for now"
    time_taken = 30  # simulate for MVP

    session = get_session_state(session_id)
    if not session:
        return {"error":"session not found"}
    
    current_q = session[0]
    max_q = session[1]
    new_q = current_q + 1
    is_completed = 1 if new_q > max_q else 0

    update_session_progress(session_id, new_q, is_completed)
    #insert_answer(session_id, question, answer, score, feedback, time_taken)

    return {
        "score": score,
        "feedback": feedback,
        "next_question_number": new_q if not is_completed else None,
        "is_completed": bool(is_completed)
    }

def fetch_session(session_id:int):
    result = get_session_with_answer(session_id)

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