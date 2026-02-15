from fastapi import APIRouter
from models.schemas import AnswerInput
from services.interview_logic import evaluate_answer
from models.schemas import SessionCreate
from services.interview_logic import start_interview
from services.interview_logic import *
router = APIRouter()

@router.get("/ping")
def ping():
    return {"message":"interviwe router working"}

@router.post("/submit_answer")
def submit_answer(data: AnswerInput):
    result = evaluate_answer(data.answer, data.session_id)
    return result

@router.post('/start-session')
def start_session(data: SessionCreate):
    return start_interview(data.candidate_name, data.domain)

@router.get("/session/{session_id}")
def get_session(session_id:int):
    return fetch_session(session_id)