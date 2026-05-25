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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                updated_at         = CURRENT_TIMESTAMP
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

        cursor.execute("UPDATE users SET profile_completed = 1 WHERE id = ?", (user_id,))
        conn.commit()

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return {"message": "Profile setup saved"}
