from openai import OpenAI
import uuid
import base64
client = OpenAI()



def text_to_speech(text, voice="alloy"):
    print("TTS INPUT:", text)
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        speed=1.15
    )
    audio_bytes = response.read()
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return b64