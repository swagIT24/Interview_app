from pydantic import BaseModel

class SubmitAnswerRequest(BaseModel):
    answer : str
    session_id : int
    question_text: str

class SessionCreate(BaseModel):
    candidate_name : str
    domain : str