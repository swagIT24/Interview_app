import json
from fastapi import APIRouter, HTTPException, Depends
from database.connections import get_connection
from services.auth_service import get_current_user
from services.plan_service import (
    generate_guided_plan,
    save_plan,
    get_today_plan,
    get_full_roadmap,
)

router = APIRouter(prefix="/plan")


@router.post("/generate")
def generate_plan(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check for existing profile
        cursor.execute("""
            SELECT target_role, target_company, skills, weak_areas,
                   preparation_weeks, daily_hours, goal_score,
                   preferred_time, experience_level
            FROM interview_profiles
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
        """, (user_id,))
        profile = cursor.fetchone()

        if not profile:
            raise HTTPException(
                status_code=400,
                detail="Please complete your profile first"
            )

        # Check for existing active plan
        cursor.execute("""
            SELECT id FROM study_plans
            WHERE user_id = %s AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        existing = cursor.fetchone()
        if existing:
            return {"plan_id": existing["id"], "existing": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    try:
        plan_days, goal_score, prep_weeks = generate_guided_plan(dict(profile))
        plan_id = save_plan(user_id, plan_days, goal_score, prep_weeks)
        return {"plan_id": plan_id, "existing": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/today")
def today_plan(user_id: int = Depends(get_current_user)):
    try:
        data = get_today_plan(user_id)
        if data is None:
            return {"has_plan": False}
        return {"has_plan": True, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roadmap")
def roadmap(user_id: int = Depends(get_current_user)):
    try:
        data = get_full_roadmap(user_id)
        if data is None:
            return {"has_plan": False}
        return {"has_plan": True, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
