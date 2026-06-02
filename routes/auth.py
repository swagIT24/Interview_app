from fastapi import APIRouter, HTTPException, Response, Request, Depends
from models.auth_schemas import RegisterRequest, LoginRequest, TokenResponse
from services.auth_service import hash_password, verify_password, create_access_token
from database.connections import create_user, get_user_by_email
from services.auth_service import create_refresh_token, decode_access_token, verify_refresh_token
from database.connections import get_connection
from services.auth_service import get_current_user
from services.limiter import limiter

router = APIRouter()


@router.post("/register")
@limiter.limit("3/minute")
def register(request: Request, data: RegisterRequest):

    existing_user = get_user_by_email(data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(data.password)
    user_id = create_user(data.name, data.email, hashed_pw)

    return {"message": "User registered successfully", "user_id": user_id}


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, data: LoginRequest, response: Response):

    user = get_user_by_email(data.email)

    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    user_id, email, hashed_pw = user

    if not verify_password(data.password, hashed_pw):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # ✅ create tokens
    access_token = create_access_token({"sub": str(user_id)})
    refresh_token = create_refresh_token(user_id)

    # ✅ save refresh token in DB and fetch profile_completed
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET refresh_token = %s
        WHERE id = %s
    """, (refresh_token, user_id))

    cursor.execute("SELECT profile_completed FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    profile_completed = bool(row[0]) if row and row[0] else False

    conn.commit()
    conn.close()

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="strict",
        secure=False
    )

    return {
        "message": "Login successful",
        "user_id": user_id,
        "email": email,
        "refresh_token": refresh_token,
        "profile_completed": profile_completed
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.post("/refresh-token")
async def refresh_token(request: Request, response: Response):

    # ✅ FIXED LINE
    body = await request.json()

    refresh_token = body.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    # Verify JWT signature and expiry before touching the DB
    user_id = verify_refresh_token(refresh_token)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM users WHERE refresh_token = %s AND id = %s
    """, (refresh_token, user_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access_token = create_access_token({"sub": str(user_id)})

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="strict",
        secure=False
    )

    return {"message": "Token refreshed"}


@router.get("/me")
def get_me(request: Request):
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")

    payload = decode_access_token(token)
    user_id = payload.get("sub")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, onboarding_completed, profile_completed FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "onboarding_completed": row[3],
        "profile_completed": bool(row[4]) if row[4] else False
    }


@router.post("/complete-onboarding")
def complete_onboarding(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET onboarding_completed = 1 WHERE id = %s
    """, (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Onboarding complete"}


@router.get("/profile-status")
def profile_status(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT profile_completed FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return {"profile_completed": bool(row[0]) if row and row[0] else False}


@router.post("/complete-profile")
def complete_profile(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET profile_completed = 1 WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Profile complete"}