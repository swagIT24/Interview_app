import resend
import os
from dotenv import load_dotenv
import random
from database.connections import get_connection
from datetime import datetime, timedelta

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def send_otp_email(to_email, otp):
    resend.Emails.send({
        "from": "Opunto <onboarding@resend.dev>",
        "to": to_email,
        "subject": "Your Opunto Verification Code",
        "html": f"<p>Your OTP for Opunto registration is: <strong>{otp}</strong></p><p>This code expires in 5 minutes.</p>"
    })


def generate_otp():
    return str(random.randint(100000, 999999))


def create_otp_record(email):
    otp = generate_otp()
    conn = get_connection()
    cursor =conn.cursor()
    cursor.execute("""
        INSERT INTO otp_verifications (email, otp_code)
        VALUES (%s,%s)
    """, (email,otp))
    conn.commit()
    cursor.close()
    conn.close()
    return otp

def verify_otp(email, otp_code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, created_at FROM otp_verifications
        WHERE email =%s AND otp_code =%s AND verified = 0
        ORDER BY created_at DESC
        LIMIT 1
    """, (email, otp_code))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return False, "Invalid OTP"

    otp_id, created_at = row[0], row[1]

    if datetime.now() - created_at > timedelta(minutes=5):
        cursor.close()
        conn.close()
        return False, "OTP expired"

    cursor.execute("UPDATE otp_verifications SET verified = 1 WHERE id = %s", (otp_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return True, "Verified"