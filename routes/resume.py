from fastapi import APIRouter, UploadFile, File, Request
from services.resume_service import extract_text_from_pdf
from services.auth_service import decode_access_token
from database.connections import get_connection

router = APIRouter()

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
    SET resume_text = ?
    WHERE id = ?
    """, (text, user_id))

    conn.commit()
    conn.close()

    
    return {"message": "Resume uploaded successfully", "text_preview": text[:200]}