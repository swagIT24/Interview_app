from pydantic import BaseModel, Field

class SubmitAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=5000)
    session_id: int
    question_text: str = Field(..., max_length=1000)

class SessionCreate(BaseModel):
    candidate_name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=200)