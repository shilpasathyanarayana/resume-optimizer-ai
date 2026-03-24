from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json

from app.config import settings
from app.database import get_db
from jose import jwt, JWTError

router = APIRouter(prefix="/api/resume", tags=["resume"])

security = HTTPBearer()

# ── Auth (same as resume.py) ───────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        user_id = payload.get("user_id")
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please log in again.")

    result = await db.execute(
        text("SELECT id, name, email, plan FROM users WHERE (id = :user_id OR email = :email) AND is_active = 1"),
        {"user_id": user_id, "email": sub}
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

# ── Schemas ────────────────────────────────────────────────────────────────────

class ResumeHistoryItem(BaseModel):
    id: int
    original_filename: Optional[str] = None
    job_title: Optional[str] = None
    ats_score: Optional[int] = None
    missing_keywords: Optional[List[str]] = None
    file_format: Optional[str] = None
    status: str
    created_at: datetime

class ResumeHistoryResponse(BaseModel):
    resumes: List[ResumeHistoryItem]
    total: int

class ResumeDetailResponse(BaseModel):
    id: int
    original_filename: Optional[str] = None
    original_text: str
    job_title: Optional[str] = None
    job_description: str
    ats_score: Optional[int] = None
    missing_keywords: Optional[List[str]] = None
    improvements: Optional[List[str]] = None
    optimized_text: Optional[str] = None
    file_format: Optional[str] = None
    status: str
    created_at: datetime

# ── History Endpoint ───────────────────────────────────────────────────────────

@router.get("/history", response_model=ResumeHistoryResponse)
async def get_resume_history(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all resume optimisations for the logged-in user, newest first.
    """
    result = await db.execute(
        text("""
            SELECT id, original_filename, job_title, ats_score,
                   missing_keywords, file_format, status, created_at
            FROM resumes
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": user.id}
    )
    rows = result.fetchall()

    items = []
    for row in rows:
        # missing_keywords is stored as JSON string in DB
        keywords = row.missing_keywords
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except (json.JSONDecodeError, TypeError):
                keywords = []

        items.append(ResumeHistoryItem(
            id=row.id,
            original_filename=row.original_filename,
            job_title=row.job_title,
            ats_score=row.ats_score,
            missing_keywords=keywords or [],
            file_format=row.file_format,
            status=row.status,
            created_at=row.created_at,
        ))

    return ResumeHistoryResponse(resumes=items, total=len(items))

# ── Detail Endpoint ────────────────────────────────────────────────────────────

@router.get("/history/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume_detail(
    resume_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns full detail for a single resume. Enforces ownership — users can
    only fetch their own records.
    """
    result = await db.execute(
        text("""
            SELECT id, original_filename, original_text, job_title,
                   job_description, ats_score, missing_keywords, improvements,
                   optimized_text, file_format, status, created_at
            FROM resumes
            WHERE id = :resume_id AND user_id = :user_id
        """),
        {"resume_id": resume_id, "user_id": user.id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Resume not found.")

    def parse_json_field(val):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []
        return val or []

    return ResumeDetailResponse(
        id=row.id,
        original_filename=row.original_filename,
        original_text=row.original_text,
        job_title=row.job_title,
        job_description=row.job_description,
        ats_score=row.ats_score,
        missing_keywords=parse_json_field(row.missing_keywords),
        improvements=parse_json_field(row.improvements),
        optimized_text=row.optimized_text,
        file_format=row.file_format,
        status=row.status,
        created_at=row.created_at,
    )

 
# ── DELETE ALL HISTORY ────────────────────────────────────────────────────────
 
@router.delete(
    "/history",
    summary="Delete all resume optimisation history for the logged-in user",
)
async def delete_resume_history(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("DELETE FROM resumes WHERE user_id = :user_id"),
        {"user_id": user.id}
    )
    await db.commit()
    return {"message": "Optimisation history deleted successfully."}
 