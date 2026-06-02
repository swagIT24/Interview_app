from datetime import date, timedelta
from fastapi import APIRouter, Depends
from services.auth_service import get_current_user
from database.connections import get_connection

router = APIRouter(prefix="/dashboard")

_FOCUS_MAP = {
    "depth":        "Practice explaining tradeoffs for every technique you mention",
    "examples":     "Add a real story to every answer — use STAR format",
    "clarity":      "Structure answers: situation → action → result",
    "completeness": "Read each question fully — answer every part asked",
}


@router.get("/stats")
def get_dashboard_stats(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        today = date.today()
        week_ago    = today - timedelta(days=7)
        two_wks_ago = today - timedelta(days=14)

        # ── Sessions ──────────────────────────────────────────────────────────

        # is_completed is INTEGER DEFAULT 0 → compare with 1 (not TRUE)
        cursor.execute("""
            SELECT COUNT(*) FROM interview_sessions
            WHERE user_id = %s AND is_completed = 1
        """, (user_id,))
        total_sessions = cursor.fetchone()[0] or 0
        print(f"DEBUG total_sessions: {total_sessions}")

        cursor.execute("""
            SELECT COUNT(*) FROM interview_sessions
            WHERE user_id = %s AND is_completed = 1
              AND created_at::date >= %s
        """, (user_id, week_ago))
        sessions_this_week = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(*) FROM interview_sessions
            WHERE user_id = %s AND is_completed = 1
              AND created_at::date >= %s AND created_at::date < %s
        """, (user_id, two_wks_ago, week_ago))
        sessions_last_week = cursor.fetchone()[0] or 0

        sessions_delta = sessions_this_week - sessions_last_week

        # ── Scores ───────────────────────────────────────────────────────────

        cursor.execute("""
            SELECT ROUND(AVG(NULLIF(a.score, 0))::NUMERIC, 1)
            FROM interview_answers a
            JOIN interview_sessions s ON a.session_id = s.id
            WHERE s.user_id = %s
        """, (user_id,))
        avg_score = float(cursor.fetchone()[0] or 0)

        cursor.execute("""
            SELECT ROUND(AVG(NULLIF(a.score, 0))::NUMERIC, 1)
            FROM interview_answers a
            JOIN interview_sessions s ON a.session_id = s.id
            WHERE s.user_id = %s AND s.created_at::date >= %s
        """, (user_id, week_ago))
        avg_score_this_week = float(cursor.fetchone()[0] or 0)

        cursor.execute("""
            SELECT ROUND(AVG(NULLIF(a.score, 0))::NUMERIC, 1)
            FROM interview_answers a
            JOIN interview_sessions s ON a.session_id = s.id
            WHERE s.user_id = %s
              AND s.created_at::date >= %s AND s.created_at::date < %s
        """, (user_id, two_wks_ago, week_ago))
        avg_score_last_week = float(cursor.fetchone()[0] or 0)

        avg_score_delta = round(avg_score_this_week - avg_score_last_week, 1)

        cursor.execute("""
            SELECT MAX(a.score)
            FROM interview_answers a
            JOIN interview_sessions s ON a.session_id = s.id
            WHERE s.user_id = %s AND a.score IS NOT NULL
        """, (user_id,))
        best_score = int(cursor.fetchone()[0] or 0)

        # ── Streak ────────────────────────────────────────────────────────────

        cursor.execute("""
            SELECT DISTINCT created_at::date AS session_date
            FROM interview_sessions
            WHERE user_id = %s AND is_completed = 1
            ORDER BY session_date DESC
        """, (user_id,))
        session_dates = {row[0] for row in cursor.fetchall()}

        current_streak = 0
        start = today if today in session_dates else today - timedelta(days=1)
        if start in session_dates:
            check = start
            while check in session_dates:
                current_streak += 1
                check -= timedelta(days=1)

        day_letters = ["M", "T", "W", "T", "F", "S", "S"]
        streak_days = [
            {"day": day_letters[(today - timedelta(days=i)).weekday()],
             "active": (today - timedelta(days=i)) in session_dates}
            for i in range(6, -1, -1)
        ]

        # ── Score trend (last 5 completed sessions, oldest → newest) ─────────

        cursor.execute("""
            SELECT s.id, s.domain, s.created_at,
                   ROUND(AVG(NULLIF(a.score, 0))::NUMERIC, 1) AS avg_score
            FROM interview_sessions s
            LEFT JOIN interview_answers a ON a.session_id = s.id
            WHERE s.user_id = %s AND s.is_completed = 1
            GROUP BY s.id, s.domain, s.created_at
            ORDER BY s.created_at DESC
            LIMIT 5
        """, (user_id,))
        trend_rows = cursor.fetchall()
        score_trend = [
            {
                "session_number": i + 1,
                "avg_score": float(row["avg_score"] or 0),
                "domain": row["domain"] or "General",
                "date": row["created_at"].strftime("%b %d") if row["created_at"] else "",
            }
            for i, row in enumerate(reversed(trend_rows))
        ]
        print(f"DEBUG score_trend rows: {len(score_trend)}")

        # ── Profile / journey ─────────────────────────────────────────────────

        cursor.execute("""
            SELECT goal_score, target_role, target_company, weak_areas
            FROM interview_profiles
            WHERE user_id = %s
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id,))
        prof = cursor.fetchone()

        goal_score     = int((prof["goal_score"]     or 10) if prof else 10)
        target_role    = str((prof["target_role"]    or "")  if prof else "")
        target_company = str((prof["target_company"] or "")  if prof else "")
        weak_areas     = str((prof["weak_areas"]     or "")  if prof else "")

        # goal_score from DB can be on old /15 scale; normalise to /10 if >10
        effective_goal = min(goal_score, 10) if goal_score <= 10 else round(goal_score / 15 * 10, 1)
        journey_progress = min(int(round(avg_score / effective_goal * 100)) if effective_goal else 0, 100)

        if journey_progress < 25:
            journey_stage = "beginner_zone"
        elif journey_progress < 51:
            journey_stage = "skill_builder"
        elif journey_progress <= 80:
            journey_stage = "expert_territory"
        else:
            journey_stage = "dream_job"

        # ── Today's focus (most common weakness, last 5 sessions) ─────────────

        cursor.execute("""
            WITH last5 AS (
                SELECT id FROM interview_sessions
                WHERE user_id = %s AND is_completed = 1
                ORDER BY created_at DESC LIMIT 5
            )
            SELECT a.weakest_dimension, COUNT(*) AS cnt
            FROM interview_answers a
            JOIN last5 ON a.session_id = last5.id
            WHERE a.weakest_dimension IS NOT NULL
            GROUP BY a.weakest_dimension
            ORDER BY cnt DESC
            LIMIT 1
        """, (user_id,))
        focus_row = cursor.fetchone()

        common_weakness = focus_row["weakest_dimension"] if focus_row else None
        if common_weakness:
            focus_msg = _FOCUS_MAP.get(
                common_weakness,
                f"Review core {target_role or 'interview'} concepts before today's session"
            )
            if common_weakness == "correctness":
                focus_msg = f"Review core {target_role or 'interview'} concepts before today's session"
        else:
            focus_msg = "Start a session to get personalised focus recommendations"

        # ── Recent sessions ───────────────────────────────────────────────────

        cursor.execute("""
            SELECT s.domain, s.created_at,
                   ROUND(AVG(NULLIF(a.score, 0))::NUMERIC, 1) AS avg_score
            FROM interview_sessions s
            LEFT JOIN interview_answers a ON a.session_id = s.id
            WHERE s.user_id = %s AND s.is_completed = 1
            GROUP BY s.id, s.domain, s.created_at
            ORDER BY s.created_at DESC
            LIMIT 5
        """, (user_id,))
        recent_rows = cursor.fetchall()

        recent_sessions = []
        for row in recent_rows:
            sc = float(row["avg_score"] or 0)
            recent_sessions.append({
                "domain":      row["domain"] or "General",
                "date":        row["created_at"].strftime("%b %d") if row["created_at"] else "",
                "avg_score":   sc,
                "score_color": "green" if sc >= 7 else "amber" if sc >= 5 else "red",
            })

        return {
            # sessions
            "total_sessions":      total_sessions,
            "sessions_this_week":  sessions_this_week,
            "sessions_last_week":  sessions_last_week,
            "sessions_delta":      sessions_delta,
            # scores
            "avg_score":           avg_score,
            "avg_score_this_week": avg_score_this_week,
            "avg_score_last_week": avg_score_last_week,
            "avg_score_delta":     avg_score_delta,
            "best_score":          best_score,
            # streak
            "current_streak":      current_streak,
            "streak_days":         streak_days,
            # trend
            "score_trend":         score_trend,
            # journey
            "goal_score":          goal_score,
            "current_avg":         avg_score,
            "journey_progress":    journey_progress,
            "journey_stage":       journey_stage,
            # profile
            "target_role":         target_role,
            "target_company":      target_company,
            "weak_areas":          weak_areas,
            # focus
            "today_focus":         focus_msg,
            "common_weakness":     common_weakness,
            # recent
            "recent_sessions":     recent_sessions,
        }

    finally:
        conn.close()
