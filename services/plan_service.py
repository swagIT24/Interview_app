import json
import math
from datetime import date, timedelta

from database.connections import get_connection

_PHASE_DESCRIPTIONS = {
    "baseline":   "Assess all topics and identify weak areas",
    "foundation": "Build core understanding on weak topics",
    "intensive":  "Advanced practice with tradeoffs and depth",
    "mock":       "Full interview simulation under pressure",
}

_SESSION_TYPES = {
    "baseline":   "assessment",
    "foundation": "practice",
    "intensive":  "intensive",
    "mock":       "mock_interview",
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_topic_pool(topics, weak_areas):
    """Return topic list with weak_areas appearing twice."""
    pool = list(topics) if topics else ["General"]
    for w in weak_areas:
        if w:
            pool.append(w)
    return pool or ["General"]


def _sessions_per_day(daily_hours):
    if daily_hours >= 5:
        return 3
    if daily_hours >= 3:
        return 2
    return 1


def _phase_schedule(prep_weeks, experience_level):
    """
    Returns list of (phase_name, num_days, difficulty) tuples.
    Upgrades beginner → intermediate when experience_level >= 4.
    """
    upgrade = experience_level >= 4

    def diff(d):
        return "intermediate" if (upgrade and d == "beginner") else d

    total = prep_weeks * 7

    if prep_weeks == 1:
        return [
            ("intensive", total - 2, diff("intermediate")),
            ("mock",      2,         "advanced"),
        ]
    if prep_weeks == 2:
        return [
            ("baseline",  3, diff("beginner")),
            ("intensive", 8, diff("intermediate")),
            ("mock",      3, "advanced"),
        ]
    if prep_weeks == 3:
        return [
            ("baseline",   5, diff("beginner")),
            ("foundation", 7, diff("intermediate")),
            ("intensive",  7, diff("intermediate")),
            ("mock",       2, "advanced"),
        ]
    # 4+ weeks
    return [
        ("baseline",   7,                    diff("beginner")),
        ("foundation", (prep_weeks - 3) * 7, diff("intermediate")),
        ("intensive",  7,                    "advanced"),
        ("mock",       7,                    "advanced"),
    ]


# ── Function 1 ────────────────────────────────────────────────────────────────

def generate_guided_plan(profile):
    """
    Takes an interview_profiles row (dict-like).
    Returns (plan_days list, goal_score, prep_weeks).
    """
    topics         = json.loads(profile.get("skills") or "[]")
    weak_areas     = json.loads(profile.get("weak_areas") or "[]")
    prep_weeks     = int(profile.get("preparation_weeks") or 4)
    daily_hours    = float(profile.get("daily_hours") or 2)
    goal_score     = int(profile.get("goal_score") or 8)
    experience_level = float(profile.get("experience_level") or 3)

    if goal_score > 10:
        goal_score = round(goal_score / 15 * 10)

    sessions_per_day = _sessions_per_day(daily_hours)
    topic_pool       = _build_topic_pool(topics, weak_areas)
    phases           = _phase_schedule(prep_weeks, experience_level)

    today     = date.today()
    plan_days = []
    day_num   = 1
    topic_idx = 0

    for phase_name, num_days, difficulty in phases:
        session_type = _SESSION_TYPES[phase_name]
        for _ in range(num_days):
            for _ in range(sessions_per_day):
                if phase_name == "mock":
                    topic = "mixed"
                else:
                    topic = topic_pool[topic_idx % len(topic_pool)]
                    topic_idx += 1

                plan_days.append({
                    "day_number":       day_num,
                    "date":             today + timedelta(days=day_num - 1),
                    "phase":            phase_name,
                    "topic":            topic,
                    "difficulty":       difficulty,
                    "session_type":     session_type,
                    "questions_count":  5,
                    "is_completed":     False,
                    "score_achieved":   None,
                    "next_review_date": None,
                })
            day_num += 1

    return plan_days, goal_score, prep_weeks


# ── Function 2 ────────────────────────────────────────────────────────────────

def save_plan(user_id, plan_days, goal_score, prep_weeks):
    """
    Persists plan to study_plans + study_plan_days.
    Returns the new plan_id.
    """
    today      = date.today()
    end_date   = today + timedelta(days=prep_weeks * 7)
    total_days = prep_weeks * 7

    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO study_plans
                (user_id, plan_type, status, start_date, end_date,
                 target_score, total_days, total_sessions)
            VALUES (%s, 'guided', 'active', %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, today, end_date, goal_score, total_days, len(plan_days)))

        plan_id = cursor.fetchone()[0]

        for day in plan_days:
            cursor.execute("""
                INSERT INTO study_plan_days
                    (plan_id, user_id, day_number, date, phase, topic,
                     difficulty, session_type, questions_count,
                     is_completed, score_achieved, next_review_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                plan_id,
                user_id,
                day["day_number"],
                day["date"],
                day["phase"],
                day["topic"],
                day["difficulty"],
                day["session_type"],
                day["questions_count"],
                day["is_completed"],
                day["score_achieved"],
                day["next_review_date"],
            ))

        cursor.execute("""
            UPDATE interview_profiles
            SET plan_type          = 'guided',
                plan_generated_at  = NOW()
            WHERE user_id = %s
        """, (user_id,))

        conn.commit()
        return plan_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Function 3 ────────────────────────────────────────────────────────────────

def get_today_plan(user_id):
    """
    Returns today's incomplete sessions plus plan metadata.
    Returns None if no active plan exists.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, total_days, end_date
            FROM study_plans
            WHERE user_id = %s AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        plan = cursor.fetchone()
        if not plan:
            return None

        plan_id    = plan["id"]
        total_days = plan["total_days"]
        end_date   = plan["end_date"]

        cursor.execute("""
            SELECT *
            FROM study_plan_days
            WHERE user_id = %s
              AND date = CURRENT_DATE
              AND is_completed = FALSE
            ORDER BY day_number ASC
        """, (user_id,))
        rows = cursor.fetchall()
        today_sessions = [dict(r) for r in rows]

        days_remaining = (end_date - date.today()).days
        current_day    = today_sessions[0]["day_number"] if today_sessions else 0
        phase          = today_sessions[0]["phase"]      if today_sessions else None

        return {
            "today_sessions": today_sessions,
            "current_day":    current_day,
            "total_days":     total_days,
            "phase":          phase,
            "days_remaining": max(days_remaining, 0),
        }

    finally:
        conn.close()


# ── Function 4 ────────────────────────────────────────────────────────────────

def get_full_roadmap(user_id):
    """
    Returns the full week-by-week roadmap for the user's active plan.
    Returns None if no active plan exists.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, start_date, end_date, target_score, total_days
            FROM study_plans
            WHERE user_id = %s AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        plan = cursor.fetchone()
        if not plan:
            return None

        plan_id = plan["id"]
        today   = date.today()

        cursor.execute("""
            SELECT *
            FROM study_plan_days
            WHERE plan_id = %s
            ORDER BY day_number ASC
        """, (plan_id,))
        all_days = [dict(r) for r in cursor.fetchall()]

        # Determine current day number
        today_days  = [d for d in all_days if d["date"] == today]
        current_day = today_days[0]["day_number"] if today_days else 0
        current_phase = today_days[0]["phase"] if today_days else (
            all_days[0]["phase"] if all_days else ""
        )

        # Group by week
        weeks_map = {}
        for day in all_days:
            wk = math.ceil(day["day_number"] / 7)
            if wk not in weeks_map:
                weeks_map[wk] = []
            day["is_today"] = (day["date"] == today)
            weeks_map[wk].append(day)

        weeks = []
        for wk in sorted(weeks_map):
            days_in_week = weeks_map[wk]
            phase        = days_in_week[0]["phase"]
            weeks.append({
                "week_number":       wk,
                "phase":             phase,
                "phase_description": _PHASE_DESCRIPTIONS.get(phase, ""),
                "days":              days_in_week,
            })

        return {
            "plan": {
                "start_date":   str(plan["start_date"]),
                "end_date":     str(plan["end_date"]),
                "target_score": plan["target_score"],
                "total_days":   plan["total_days"],
                "current_day":  current_day,
                "phase":        current_phase,
            },
            "weeks": weeks,
        }

    finally:
        conn.close()


# ── Function 5 ────────────────────────────────────────────────────────────────

def update_day_completion(plan_day_id, score):
    """
    Marks a study_plan_days row as completed and sets next_review_date
    based on spaced-repetition intervals derived from the score.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE study_plan_days
            SET is_completed     = TRUE,
                score_achieved   = %s,
                next_review_date = CASE
                    WHEN %s <= 4 THEN CURRENT_DATE + 1
                    WHEN %s <= 7 THEN CURRENT_DATE + 3
                    ELSE CURRENT_DATE + 7
                END
            WHERE id = %s
        """, (score, score, score, plan_day_id))

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
