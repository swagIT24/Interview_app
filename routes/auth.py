from fastapi import APIRouter, HTTPException, Response
from models.auth_schemas import RegisterRequest, LoginRequest, TokenResponse
from services.auth_service import hash_password, verify_password, create_access_token
from database.connections import create_user, get_user_by_email

router = APIRouter()


@router.post("/register")
def register(data: RegisterRequest):

    existing_user = get_user_by_email(data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(data.password)
    user_id = create_user(data.email, hashed_pw)

    return {"message": "User registered successfully", "user_id": user_id}


@router.post("/login")
def login(data: LoginRequest, response: Response):

    user = get_user_by_email(data.email)

    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    user_id, email, hashed_pw = user

    if not verify_password(data.password, hashed_pw):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = create_access_token({"sub": str(user_id)})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=False  # set True in production (HTTPS)
    )

    return {
        "message": "Login successful",
        "user_id": user_id,
        "email": email
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="strict",
    )
    return {"message": "Logged out successfully"}
