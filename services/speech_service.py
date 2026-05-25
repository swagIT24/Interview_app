from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def speech_to_text(filename: str, audio_bytes: bytes, content_type: str):
    try:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=(filename, audio_bytes, content_type),
            language="en"
        )
        return transcript.text
    except Exception as e:
        raise Exception("Speech-to-text failed") from e