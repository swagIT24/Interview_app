import sqlite3
import json

DB_NAME = "interview.db"

def get_connection():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False,
        isolation_level=None   # 🔥 ADD THIS
    )
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")

    # ================= USERS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT NOT NULL,

        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,

        refresh_token TEXT,

        profile_completed INTEGER DEFAULT 0,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ================= INTERVIEW PROFILES =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER NOT NULL,

        target_role TEXT NOT NULL,
        experience_level REAL NOT NULL,

        desired_goals TEXT NOT NULL DEFAULT '[]',

        skills TEXT DEFAULT '[]',
        strong_areas TEXT DEFAULT '[]',
        weak_areas TEXT DEFAULT '[]',
        areas_to_improve TEXT DEFAULT '[]',

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        UNIQUE(user_id, target_role),

        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # ================= INTERVIEW SESSIONS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER,

        candidate_name TEXT,
        domain TEXT,

        current_question_number INTEGER DEFAULT 1,
        max_questions INTEGER DEFAULT 20,

        is_completed INTEGER DEFAULT 0,

        asked_questions TEXT DEFAULT '[]',

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ================= INTERVIEW ANSWERS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        session_id INTEGER,

        question TEXT,
        answer TEXT,

        score INTEGER,
        feedback TEXT,

        time_taken INTEGER,

        FOREIGN KEY (session_id) REFERENCES interview_sessions(id)
    )
    """)

    # ================= JOB APPLICATIONS =================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER NOT NULL,

        company TEXT NOT NULL,
        role TEXT NOT NULL,

        status TEXT NOT NULL DEFAULT 'Applied',

        notes TEXT,

        date_applied DATE,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


def create_user(name: str, email: str, hashed_password: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (name, email, hashed_password)
        VALUES (?, ?, ?)
    """, (name, email, hashed_password))

    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    return user_id


def get_user_by_email(email: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, hashed_password
        FROM users
        WHERE email = ?
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
        VALUES (?, ?, ?, ?)
        """, (user_id, candidate_name, domain, "[]"))

        conn.commit()
        return cursor.lastrowid

    finally:
        cursor.close()
        conn.close()


def insert_answer(cursor, session_id: int, question: str, answer: str,
                  score: int, feedback: str, time_taken: int):

    cursor.execute("""
    INSERT INTO interview_answers (session_id, question, answer, score, feedback, time_taken)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, question, answer, score, feedback, time_taken))


def get_session_with_answer(session_id: int, user_id: int):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # fetch session info with ownership check
    cursor.execute("""
        SELECT * FROM interview_sessions
        WHERE id = ? AND user_id = ?
    """, (session_id, user_id))

    session = cursor.fetchone()

    if not session:
        conn.close()
        return None

    # fetch answers
    cursor.execute("""
        SELECT question, answer, score, feedback, time_taken
        FROM interview_answers
        WHERE session_id = ?
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


def migrate_schema():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(interview_sessions)")
    columns = [col[1] for col in cursor.fetchall()]
    try:
        cursor.execute("ALTER TABLE interview_sessions ADD COLUMN current_question_number INTEGER DEFAULT 1")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE interview_sessions ADD COLUMN max_questions INTEGER DEFAULT 20")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE interview_sessions ADD COLUMN is_completed INTEGER DEFAULT 0")
    except:
        pass
    
    
    try:
        cursor.execute("ALTER TABLE interview_answers ADD COLUMN question_embedding TEXT")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE interview_answers ADD COLUMN  difficulty_level TEXT DEFAULT 'easy'")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE interview_sessions ADD COLUMN asked_questions TEXT DEFAULT '[]'")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN resume_text TEXT")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 0")
    except:
        pass

    if "user_id" not in columns:
        try:
            cursor.execute("ALTER TABLE interview_sessions ADD COLUMN user_id INTEGER")
        except:
            pass


    conn.commit()
    conn.close()

def update_session_progress(session_id: int, user_id: int, new_question_number: int, is_completed: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE interview_sessions
        SET current_question_number = ?, is_completed = ?
        WHERE id = ? AND user_id = ?
    """, (new_question_number, is_completed, session_id, user_id))

    conn.commit()
    conn.close()


def get_session_state(user_id: int, session_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT current_question_number, difficulty_level, is_completed
    FROM interview_sessions
    WHERE id = ? AND user_id = ?
    """, (session_id, user_id))

    session = cursor.fetchone()
    conn.close()

    return session

def get_last_n_scores(cursor, session_id: int, n: int):
    cursor.execute("""
        SELECT score
        FROM interview_answers
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (session_id, n))

    rows = cursor.fetchall()
    return [row[0] for row in rows]
