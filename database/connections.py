import json
import psycopg2
import os
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ================= USERS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id                   SERIAL PRIMARY KEY,
        name                 TEXT NOT NULL,
        email                TEXT UNIQUE NOT NULL,
        hashed_password      TEXT NOT NULL,
        refresh_token        TEXT,
        profile_completed    INTEGER DEFAULT 0,
        onboarding_completed INTEGER DEFAULT 0,
        resume_text          TEXT,
        created_at           TIMESTAMP DEFAULT NOW()
    )
    """)

    # ================= INTERVIEW PROFILES =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_profiles (
        id                SERIAL PRIMARY KEY,
        user_id           INTEGER NOT NULL REFERENCES users(id),
        target_role       TEXT NOT NULL,
        experience_level  REAL NOT NULL DEFAULT 0,
        desired_goals     TEXT NOT NULL DEFAULT '[]',
        skills            TEXT DEFAULT '[]',
        strong_areas      TEXT DEFAULT '[]',
        weak_areas        TEXT DEFAULT '[]',
        areas_to_improve  TEXT DEFAULT '[]',
        target_company    TEXT DEFAULT '',
        preparation_weeks INTEGER DEFAULT 4,
        daily_hours       REAL DEFAULT 2,
        preferred_time    TEXT DEFAULT 'evening',
        goal_score        INTEGER DEFAULT 12,
        confidence_levels TEXT DEFAULT '{}',
        study_plan        TEXT DEFAULT '{}',
        created_at        TIMESTAMP DEFAULT NOW(),
        updated_at        TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, target_role)
    )
    """)

    # ================= INTERVIEW SESSIONS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_sessions (
        id                      SERIAL PRIMARY KEY,
        user_id                 INTEGER REFERENCES users(id),
        candidate_name          TEXT,
        domain                  TEXT,
        current_question_number INTEGER DEFAULT 1,
        max_questions           INTEGER DEFAULT 10,
        is_completed            INTEGER DEFAULT 0,
        asked_questions         TEXT DEFAULT '[]',
        created_at              TIMESTAMP DEFAULT NOW()
    )
    """)

    # ================= INTERVIEW ANSWERS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_answers (
        id               SERIAL PRIMARY KEY,
        session_id       INTEGER REFERENCES interview_sessions(id),
        question         TEXT,
        answer           TEXT,
        score            INTEGER,
        feedback         TEXT,
        difficulty_level TEXT DEFAULT 'easy',
        time_taken       INTEGER
    )
    """)

    # ================= JOB APPLICATIONS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_applications (
        id           SERIAL PRIMARY KEY,
        user_id      INTEGER NOT NULL REFERENCES users(id),
        company      TEXT NOT NULL,
        role         TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'Applied',
        notes        TEXT,
        date_applied DATE,
        created_at   TIMESTAMP DEFAULT NOW()
    )
    """)

    # ================= STUDY PLANS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS study_plans (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        plan_type      TEXT DEFAULT 'guided',
        status         TEXT DEFAULT 'active',
        start_date     DATE,
        end_date       DATE,
        target_score   INTEGER,
        total_days     INTEGER,
        total_sessions INTEGER,
        created_at     TIMESTAMP DEFAULT NOW()
    )
    """)

    # ================= STUDY PLAN DAYS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS study_plan_days (
        id               SERIAL PRIMARY KEY,
        plan_id          INTEGER NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
        user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day_number       INTEGER,
        date             DATE,
        phase            TEXT,
        topic            TEXT,
        difficulty       TEXT,
        session_type     TEXT,
        questions_count  INTEGER DEFAULT 5,
        is_completed     BOOLEAN DEFAULT FALSE,
        score_achieved   INTEGER,
        next_review_date DATE,
        created_at       TIMESTAMP DEFAULT NOW()
    )
    """)

    # ================= OTP VERIFICATIONS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS otp_verifications (
        id         SERIAL PRIMARY KEY,
        email      TEXT NOT NULL,
        otp_code   VARCHAR(6) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        verified   INTEGER DEFAULT 0
    )
    """)

    # ================= SCHEMA PATCHES (safe on existing DBs) =================

    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS practice_count INTEGER DEFAULT 0
    """)

    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS roleplay_count INTEGER DEFAULT 0
    """)

    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0
    """)

    cursor.execute("""
        ALTER TABLE interview_profiles
        ADD COLUMN IF NOT EXISTS plan_type VARCHAR(50)
    """)

    cursor.execute("""
        ALTER TABLE interview_profiles
        ADD COLUMN IF NOT EXISTS plan_generated_at TIMESTAMP
    """)

    cursor.execute("""
        ALTER TABLE job_applications
        ADD COLUMN IF NOT EXISTS link TEXT
    """)

    conn.commit()
    conn.close()


def create_user(name: str, email: str, hashed_password: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (name, email, hashed_password)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (name, email, hashed_password))

    user_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    return user_id


def get_user_by_email(email: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, hashed_password
        FROM users
        WHERE email = %s
    """, (email,))

    user = cursor.fetchone()
    conn.close()

    return user


def create_session(user_id: int, candidate_name: str, domain: str):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO interview_sessions (user_id, candidate_name, domain, asked_questions)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (user_id, candidate_name, domain, "[]"))

        session_id = cursor.fetchone()[0]
        conn.commit()
        return session_id

    finally:
        cursor.close()
        conn.close()


def insert_answer(cursor, session_id: int, question: str, answer: str,
                  score: int, feedback: str, time_taken: int,
                  score_breakdown: dict = None, weakest_dimension: str = None,
                  model_answer_hint: str = None, analysis_text: str = None):

    cursor.execute("""
    INSERT INTO interview_answers
        (session_id, question, answer, score, feedback, time_taken,
         score_breakdown, weakest_dimension, model_answer_hint, analysis_text)
    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
    """, (
        session_id, question, answer, score, feedback, time_taken,
        json.dumps(score_breakdown) if score_breakdown else None,
        weakest_dimension,
        model_answer_hint,
        analysis_text,
    ))


def get_session_with_answer(session_id: int, user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM interview_sessions
        WHERE id = %s AND user_id = %s
    """, (session_id, user_id))

    session = cursor.fetchone()

    if not session:
        conn.close()
        return None

    cursor.execute("""
        SELECT question, answer, score, feedback, time_taken
        FROM interview_answers
        WHERE session_id = %s
        ORDER BY id ASC
    """, (session_id,))

    answers = cursor.fetchall()
    session_dict = dict(session)
    session_dict["asked_questions"] = json.loads(session_dict.get("asked_questions", "[]"))

    result = {
        "session": session_dict,
        "answers": [dict(row) for row in answers]
    }

    conn.close()
    return result


def update_session_progress(session_id: int, user_id: int, new_question_number: int, is_completed: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE interview_sessions
        SET current_question_number = %s, is_completed = %s
        WHERE id = %s AND user_id = %s
    """, (new_question_number, is_completed, session_id, user_id))

    conn.commit()
    conn.close()


def get_session_state(user_id: int, session_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT current_question_number, is_completed
        FROM interview_sessions
        WHERE id = %s AND user_id = %s
    """, (session_id, user_id))

    session = cursor.fetchone()
    conn.close()

    return session


def get_last_n_scores(cursor, session_id: int, n: int):
    cursor.execute("""
        SELECT score
        FROM interview_answers
        WHERE session_id = %s
        ORDER BY id DESC
        LIMIT %s
    """, (session_id, n))

    rows = cursor.fetchall()
    return [row[0] for row in rows]
