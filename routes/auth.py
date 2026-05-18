from fastapi import APIRouter, HTTPException, Response, Request, Depends
from models.auth_schemas import RegisterRequest, LoginRequest, TokenResponse
from services.auth_service import hash_password, verify_password, create_access_token
from database.connections import create_user, get_user_by_email
from services.auth_service import create_refresh_token, decode_access_token
from database.connections import get_connection
from services.auth_service import get_current_user
router = APIRouter()


@router.post("/register")
def register(data: RegisterRequest):

    existing_user = get_user_by_email(data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(data.password)
    user_id = create_user(data.name, data.email, hashed_pw)

    return {"message": "User registered successfully", "user_id": user_id}


@router.post("/login")
def login(data: LoginRequest, response: Response):

    user = get_user_by_email(data.email)

    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    user_id, email, hashed_pw = user

    if not verify_password(data.password, hashed_pw):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # ✅ create tokens
    access_token = create_access_token({"sub": str(user_id)})
    refresh_token = create_refresh_token()

    # ✅ save refresh token in DB
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET refresh_token = ?
        WHERE id = ?
    """, (refresh_token, user_id))

    conn.commit()
    conn.close()

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="strict",
        secure=False
    )

    # ✅ RETURN refresh token (THIS WAS MISSING)
    return {
        "message": "Login successful",
        "user_id": user_id,
        "email": email,
        "refresh_token": refresh_token
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

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM users WHERE refresh_token = ?
    """, (refresh_token,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = row[0]

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
    cursor.execute("SELECT id, name, email, onboarding_completed FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "onboarding_completed": row[3] 
    }


@router.post("/complete-onboarding")
def complete_onboarding(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET onboarding_completed = 1 WHERE id = ?
    """, (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Onboarding complete"}