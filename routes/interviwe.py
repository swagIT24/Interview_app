from fastapi import APIRouter
from models.schemas import SubmitAnswerRequest
from services.interview_logic import evaluate_answer
from models.schemas import SessionCreate
from services.interview_logic import start_interview
from services.interview_logic import *
router = APIRouter()

@router.get("/ping")
def ping():
    return {"message":"interviwe router working"}

@router.post("/submit-answer")
def submit_answer(data: SubmitAnswerRequest):

    evaluation = evaluate_answer(data.answer, data.session_id)

    # If session not found or error
    if "error" in evaluation:
        return evaluation

    if not evaluation["is_completed"]:
        next_question = generate_next_question(data.session_id)
    else:
        next_question = None

    return {
        **evaluation,
        "next_question": next_question
    }


@router.post('/start-session')
def start_session(data: SessionCreate):
    return start_interview(data.candidate_name, data.domain)

@router.get("/session/{session_id}")
def get_session(session_id:int):
    return fetch_session(session_id)