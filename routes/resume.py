from fastapi import APIRouter, Depends, UploadFile, File
from services.resume_service import extract_text_from_pdf
from services.auth_service import get_current_user
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
async def upload_resume(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user)
):
    file_bytes = await file.read()
    text = extract_text_from_pdf(file_bytes)

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