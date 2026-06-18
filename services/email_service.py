import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import random
from database.connections import get_connection
from datetime import datetime, timedelta

load_dotenv()

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def send_otp_email(to_email, otp):
    subject = "Your Opunto Verification Code"
    body = f"Your OTP for Opunto registration is: {otp}\n\nThis code expires in 10 minutes."
    
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_EMAIL
    msg["To"] = to_email
    
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)


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