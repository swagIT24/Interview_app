from fastapi import APIRouter
from models.schemas import SubmitAnswerRequest
from services.interview_logic import evaluate_answer
from models.schemas import SessionCreate
from services.interview_logic import start_interview
from services.interview_logic import *
from services.auth_service import get_current_user
from fastapi import Depends

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message":"interviwe router working"}

@router.post("/submit-answer")
def submit_answer(data: SubmitAnswerRequest, user_id: int = Depends(get_current_user)):

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


@router.post("/start-session")
def start_session(data: SessionCreate, user_id: int = Depends(get_current_user)):
    session_id = start_interview(user_id, data.candidate_name, data.domain)
    return {"session_id": session_id}


@router.get("/session/{session_id}")
def get_session(session_id: int, user_id: int = Depends(get_current_user)):
    return fetch_session(session_id, user_id)