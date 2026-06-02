import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from database.connections import get_connection
from services.auth_service import get_current_user

router = APIRouter()


class ProfileSetupRequest(BaseModel):
    target_role: str
    target_company: Optional[str] = ""
    experience_level: Optional[float] = 0
    skills: Optional[List[str]] = []
    confidence_levels: Optional[dict] = {}
    preparation_weeks: Optional[int] = 4
    daily_hours: Optional[float] = 2
    preferred_time: Optional[str] = "evening"
    goal_score: Optional[int] = 12
    desired_goals: Optional[List[str]] = []


@router.post("/save-profile-setup")
def save_profile_setup(data: ProfileSetupRequest, user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO interview_profiles
                (user_id, target_role, target_company, experience_level, skills,
                 confidence_levels, preparation_weeks, daily_hours, preferred_time,
                 goal_score, desired_goals, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT(user_id, target_role) DO UPDATE SET
                target_company     = excluded.target_company,
                experience_level   = excluded.experience_level,
                skills             = excluded.skills,
                confidence_levels  = excluded.confidence_levels,
                preparation_weeks  = excluded.preparation_weeks,
                daily_hours        = excluded.daily_hours,
                preferred_time     = excluded.preferred_time,
                goal_score         = excluded.goal_score,
                desired_goals      = excluded.desired_goals,
                updated_at         = NOW()
        """, (
            user_id,
            data.target_role,
            data.target_company,
            data.experience_level,
            json.dumps(data.skills),
            json.dumps(data.confidence_levels),
            data.preparation_weeks,
            data.daily_hours,
            data.preferred_time,
            data.goal_score,
            json.dumps(data.desired_goals),
        ))

        cursor.execute("UPDATE users SET profile_completed = 1 WHERE id = %s", (user_id,))
        conn.commit()

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return {"message": "Profile setup saved"}


class GoalsUpdateRequest(BaseModel):
    target_role: Optional[str] = "General"
    target_company: Optional[str] = ""
    skills: Optional[List[str]] = []
    preparation_weeks: Optional[int] = 4
    daily_hours: Optional[float] = 2
    goal_score: Optional[int] = 8
    preferred_time: Optional[str] = "evening"


@router.get("/profile/goals")
def get_profile_goals(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT target_role, target_company, skills,
                   preparation_weeks, daily_hours, goal_score, preferred_time
            FROM interview_profiles
            WHERE user_id = %s
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        raw_score = row["goal_score"] or 8
        score = round(raw_score / 15 * 10) if raw_score > 10 else raw_score
        return {
            "target_role":       row["target_role"] or "",
            "target_company":    row["target_company"] or "",
            "skills":            json.loads(row["skills"] or "[]"),
            "preparation_weeks": row["preparation_weeks"] or 4,
            "daily_hours":       float(row["daily_hours"] or 2),
            "goal_score":        max(5, min(score, 10)),
            "preferred_time":    row["preferred_time"] or "evening",
        }
    finally:
        conn.close()


@router.put("/profile/goals")
def update_profile_goals(data: GoalsUpdateRequest, user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO interview_profiles
                (user_id, target_role, target_company, skills,
                 preparation_weeks, daily_hours, goal_score, preferred_time,
                 experience_level, desired_goals, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, '[]', NOW())
            ON CONFLICT (user_id, target_role) DO UPDATE SET
                target_company    = EXCLUDED.target_company,
                skills            = EXCLUDED.skills,
                preparation_weeks = EXCLUDED.preparation_weeks,
                daily_hours       = EXCLUDED.daily_hours,
                goal_score        = EXCLUDED.goal_score,
                preferred_time    = EXCLUDED.preferred_time,
                updated_at        = NOW()
        """, (
            user_id,
            data.target_role or "General",
            data.target_company,
            json.dumps(data.skills),
            data.preparation_weeks,
            data.daily_hours,
            data.goal_score,
            data.preferred_time,
        ))
        cursor.execute("UPDATE users SET profile_completed = 1 WHERE id = %s", (user_id,))
        conn.commit()
        return {"message": "Goals updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
