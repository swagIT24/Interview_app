from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from database.connections import get_connection
from services.auth_service import get_current_user
from services.resume_tailor_service import calculate_match


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    company: str
    role: str
    status: str = "Applied"
    notes: Optional[str] = None
    date_applied: Optional[str] = None


class JobUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class TailorRequest(BaseModel):
    job_description: str


@router.post("")
def add_job(data: JobCreate, user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO job_applications (user_id, company, role, status, notes, date_applied)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, data.company, data.role, data.status, data.notes, data.date_applied))

    conn.commit()
    job_id = cursor.lastrowid
    conn.close()

    return {"message": "Job application added", "job_id": job_id}


@router.get("")
def get_jobs(user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, company, role, status, notes, date_applied, created_at
        FROM job_applications
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@router.put("/{job_id}")
def update_job(job_id: int, data: JobUpdate, user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM job_applications WHERE id = ? AND user_id = ?
    """, (job_id, user_id))

    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Job application not found")

    if data.status is not None:
        cursor.execute("""
            UPDATE job_applications SET status = ? WHERE id = ? AND user_id = ?
        """, (data.status, job_id, user_id))

    if data.notes is not None:
        cursor.execute("""
            UPDATE job_applications SET notes = ? WHERE id = ? AND user_id = ?
        """, (data.notes, job_id, user_id))

    conn.commit()
    conn.close()

    return {"message": "Job application updated"}


@router.delete("/{job_id}")
def delete_job(job_id: int, user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM job_applications WHERE id = ? AND user_id = ?
    """, (job_id, user_id))

    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Job application not found")

    cursor.execute("""
        DELETE FROM job_applications WHERE id = ? AND user_id = ?
    """, (job_id, user_id))

    conn.commit()
    conn.close()

    return {"message": "Job application deleted"}


@router.post("/tailor-resume")
async def tailor_resume(request: TailorRequest, user_id: int = Depends(get_current_user)):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT resume_text FROM users WHERE id = ?
    """, (user_id,))
 
    row = cursor.fetchone()  # ← store it in a variable
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume not found")
    resume_text = row[0]
    conn.commit()
    conn.close()
    score, matches, missing = calculate_match(resume_text, request.job_description)
    return {
    "score": score,
    "matches": matches,
    "missing": missing
}


