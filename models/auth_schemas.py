from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)


class VerifyOtpRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    otp: str = Field(..., min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    email: str
