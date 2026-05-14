from fastapi import APIRouter, UploadFile, File, Form
from services.interview_logic import process_answer
from services.interview_logic import get_next_question, update_asked_questions
from services.speech_service import speech_to_text
from services.tts_service import text_to_speech
from database.connections import get_connection
import json

router = APIRouter()

@router.post("/voice/upload")
async def upload_audio(
    session_id: int,
    file: UploadFile = File(...),
    question_text: str = Form(...)
):
    try:
        # 1. Transcribe audio
        audio_bytes = await file.read()
        text = speech_to_text(
            file.filename,
            audio_bytes,
            file.content_type
        )

        # 2. Fetch session state
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT domain, asked_questions
            FROM interview_sessions
            WHERE id = ?
        """, (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"error": "Session not found"}

        domain = row[0]
        asked_questions = json.loads(row[1]) if row[1] else []

        # 3. Evaluate answer
        evaluation = process_answer(text, session_id, question_text)

        if "error" in evaluation:
            return {"error": evaluation["error"]}

        # 4. Get next question
        question_data = get_next_question(domain, asked_questions)

        if not question_data:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE interview_sessions
                SET is_completed = 1
                WHERE id = ?
            """, (session_id,))
            conn.commit()
            conn.close()

            return {
                "transcript": text,
                "evaluation": evaluation,
                "next_question": None,
                "audio": None,
                "is_completed": True
            }

        next_question = question_data["question"]["question"]

        update_asked_questions(session_id, next_question)

        # 5. Generate TTS for next question
        try:
            audio_b64 = text_to_speech(next_question)
        except Exception as e:
            print("TTS failed:", e)
            audio_b64 = None

        return {
            "transcript": text,
            "evaluation": evaluation,
            "next_question": next_question,
            "audio": audio_b64,
            "is_completed": False
        }

    except Exception as e:
        return {"error": str(e)}