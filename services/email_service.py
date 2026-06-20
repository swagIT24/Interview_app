import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import os
from dotenv import load_dotenv
import random
from database.connections import get_connection
from datetime import datetime, timedelta

load_dotenv()

configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")

def send_otp_email(to_email, otp):
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        sender={"name": "Opunto", "email": "opuntoai@gmail.com"},
        subject="Your Opunto Verification Code",
        html_content=f"<p>Your OTP for Opunto registration is: <strong>{otp}</strong></p><p>This code expires in 5 minutes.</p>"
    )
    try:
        api_instance.send_transac_email(send_smtp_email)
    except ApiException as e:
        print(f"Brevo API error: {e}")
        raise


def generate_otp():
    return str(random.randint(100000, 999999))


def create_otp_record(email):
    otp = generate_otp()
    conn = get_connection()
    cursor = conn.cursor()
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