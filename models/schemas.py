from pydantic import BaseModel

class AnswerInput(BaseModel):
    answer : str
    session_id : int

class SessionCreate(BaseModel):
    candidate_name : str
    domain : str