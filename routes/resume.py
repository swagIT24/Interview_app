from fastapi import APIRouter, Depends, UploadFile, File, Request
from services.resume_service import extract_text_from_pdf
from services.auth_service import decode_access_token, get_current_user
from database.connections import get_connection

router = APIRouter()

@router.get("/resume-status")
def resume_status(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT resume_text FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    conn.close()
    has_resume = bool(row and row[0])
    return {"has_resume": has_resume}


@router.post("/upload-resume")
async def upload_resume(request: Request, file: UploadFile = File(...)):
    
    # read file bytes
    file_bytes = await file.read()
    
    # extract text from PDF
    text = extract_text_from_pdf(file_bytes)
    token = request.cookies.get("access_token")
    print(token)
    try:
        payload = decode_access_token(token)
        print("PAYLOAD:", payload)

    except Exception as e:
        print("ERROR:", e)
    print("RESUME TEXT:", text[:500])  # print first 500 chars to verify
    user_id = payload["sub"]
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET resume_text = %s
    WHERE id = %s
    """, (text, user_id))

    conn.commit()
    conn.close()

    
    return {"message": "Resume uploaded successfully", "text_preview": text[:200]}