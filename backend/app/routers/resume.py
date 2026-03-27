import json
import io
import PyPDF2
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Depends
from pydantic import BaseModel
from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.database import get_db
from app.routers.auth import get_current_user
from app.schemas.auth import CurrentUser
from typing import List, Optional

router = APIRouter(prefix="/resume", tags=["resume"])

FREE_MONTHLY_LIMIT = 5


# ── Schemas ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    resume_text:     str
    job_description: str

class AnalyzeResponse(BaseModel):
    ats_score:        int
    missing_keywords: List[str]
    improvements:     List[str]
    optimized_text:   str
    uses_this_month:  int
    uses_remaining:   int
    resume_id:        Optional[int] = None

class ResumeHistoryItem(BaseModel):
    id:                int
    original_filename: Optional[str]       = None
    job_title:         Optional[str]       = None
    ats_score:         Optional[int]       = None
    missing_keywords:  Optional[List[str]] = None
    file_format:       Optional[str]       = None
    status:            str
    created_at:        datetime

class ResumeHistoryResponse(BaseModel):
    resumes: List[ResumeHistoryItem]
    total:   int

class ResumeDetailResponse(BaseModel):
    id:                int
    original_filename: Optional[str]       = None
    original_text:     str
    job_title:         Optional[str]       = None
    job_description:   str
    ats_score:         Optional[int]       = None
    missing_keywords:  Optional[List[str]] = None
    improvements:      Optional[List[str]] = None
    optimized_text:    Optional[str]       = None
    file_format:       Optional[str]       = None
    status:            str
    created_at:        datetime


# ── Usage helpers ──────────────────────────────────────────────────────────────

async def get_usage_row(db: AsyncSession, user_id: int) -> dict:
    result = await db.execute(
        text("SELECT monthly_usage, usage_reset_at FROM subscriptions WHERE user_id = :id"),
        {"id": user_id}
    )
    row = result.fetchone()
    if not row:
        return {"monthly_usage": 0, "usage_reset_at": datetime.utcnow()}

    now           = datetime.utcnow()
    monthly_usage = row.monthly_usage
    reset_at      = row.usage_reset_at

    if (now - reset_at) > timedelta(days=30):
        monthly_usage = 0
        await db.execute(
            text("UPDATE subscriptions SET monthly_usage = 0, usage_reset_at = :now WHERE user_id = :id"),
            {"now": now, "id": user_id}
        )
        await db.commit()
        reset_at = now

    return {"monthly_usage": monthly_usage, "usage_reset_at": reset_at}


async def check_and_increment_usage(current_user: CurrentUser, db: AsyncSession):
    if current_user.is_pro:
        return 0, 999999

    usage         = await get_usage_row(db, current_user.id)
    monthly_usage = usage["monthly_usage"]

    if monthly_usage >= FREE_MONTHLY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {FREE_MONTHLY_LIMIT} free optimizations this month. Upgrade to Pro for unlimited access."
        )

    new_usage = monthly_usage + 1
    await db.execute(
        text("UPDATE subscriptions SET monthly_usage = monthly_usage + 1 WHERE user_id = :id"),
        {"id": current_user.id}
    )
    await db.commit()
    return new_usage, max(FREE_MONTHLY_LIMIT - new_usage, 0)


# ── Save resume ────────────────────────────────────────────────────────────────

async def save_resume(
    db: AsyncSession,
    user_id: int,
    original_text: str,
    job_description: str,
    ats_score: int,
    missing_keywords: list,
    improvements: list,
    optimized_text: str,
    original_filename: str = None,
    file_format: str = None,
) -> int:
    job_title = job_description.strip().split('\n')[0][:255] if job_description else None

    result = await db.execute(
        text("""
            INSERT INTO resumes (
                user_id, original_filename, original_text, job_title,
                job_description, ats_score, missing_keywords, improvements,
                optimized_text, file_format, status
            ) VALUES (
                :user_id, :original_filename, :original_text, :job_title,
                :job_description, :ats_score, :missing_keywords, :improvements,
                :optimized_text, :file_format, 'completed'
            )
        """),
        {
            "user_id":           user_id,
            "original_filename": original_filename,
            "original_text":     original_text,
            "job_title":         job_title,
            "job_description":   job_description,
            "ats_score":         ats_score,
            "missing_keywords":  json.dumps(missing_keywords),
            "improvements":      json.dumps(improvements),
            "optimized_text":    optimized_text,
            "file_format":       file_format,
        }
    )
    await db.commit()
    return result.lastrowid


# ── Usage endpoint ─────────────────────────────────────────────────────────────

@router.get("/usage")
async def get_usage(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_pro:
        return {
            "is_pro":          True,
            "uses_this_month": 0,
            "uses_remaining":  999999,
            "limit":           999999,
            "resets_at":       None,
        }

    usage         = await get_usage_row(db, current_user.id)
    monthly_usage = usage["monthly_usage"]
    reset_at      = usage["usage_reset_at"]

    return {
        "is_pro":          False,
        "uses_this_month": monthly_usage,
        "uses_remaining":  max(FREE_MONTHLY_LIMIT - monthly_usage, 0),
        "limit":           FREE_MONTHLY_LIMIT,
        "resets_at":       (reset_at + timedelta(days=30)).isoformat(),
    }


# ── History endpoint ───────────────────────────────────────────────────────────

@router.get("/history", response_model=ResumeHistoryResponse)
async def get_resume_history(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Resume history is a Pro feature. Upgrade to access.")

    result = await db.execute(
        text("""
            SELECT id, original_filename, job_title, ats_score,
                   missing_keywords, file_format, status, created_at
            FROM resumes
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": current_user.id}
    )
    rows  = result.fetchall()
    items = []

    for row in rows:
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


# ── Detail endpoint ────────────────────────────────────────────────────────────

@router.get("/history/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume_detail(
    resume_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Resume history is a Pro feature. Upgrade to access.")

    result = await db.execute(
        text("""
            SELECT id, original_filename, original_text, job_title,
                   job_description, ats_score, missing_keywords, improvements,
                   optimized_text, file_format, status, created_at
            FROM resumes
            WHERE id = :resume_id AND user_id = :user_id
        """),
        {"resume_id": resume_id, "user_id": current_user.id}
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


# ── Delete history endpoint ────────────────────────────────────────────────────

@router.delete("/history")
async def delete_resume_history(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("DELETE FROM resumes WHERE user_id = :user_id"),
        {"user_id": current_user.id}
    )
    await db.commit()
    return {"message": "Optimisation history deleted successfully."}


# ── AI service ─────────────────────────────────────────────────────────────────

def build_prompt(resume_text: str, job_description: str) -> str:
    return f"""Analyze this resume against the job description and return a JSON object with exactly these fields:
{{
  "ats_score": <integer 0-100>,
  "missing_keywords": ["keyword1", "keyword2"],
  "improvements": ["suggestion1", "suggestion2"],
  "optimized_text": "<full rewritten resume text>"
}}

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}"""


async def run_ai(resume_text: str, job_description: str) -> dict:
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert resume consultant. Always respond with valid JSON only — no markdown, no explanation."},
                {"role": "user",   "content": build_prompt(resume_text, job_description)}
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI provider error: {str(e)}")

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="AI returned invalid JSON. Please try again.")


# ── Analyze endpoint ───────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_resume(
    body: AnalyzeRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(body.resume_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Resume text is too short.")
    if len(body.job_description.strip()) < 50:
        raise HTTPException(status_code=422, detail="Job description is too short.")

    uses_this_month, uses_remaining = await check_and_increment_usage(current_user, db)
    result = await run_ai(body.resume_text, body.job_description)

    resume_id = await save_resume(
        db=db,
        user_id=current_user.id,
        original_text=body.resume_text,
        job_description=body.job_description,
        ats_score=int(result.get("ats_score", 0)),
        missing_keywords=result.get("missing_keywords", []),
        improvements=result.get("improvements", []),
        optimized_text=result.get("optimized_text", ""),
        file_format="txt",
    )

    return AnalyzeResponse(
        ats_score=int(result.get("ats_score", 0)),
        missing_keywords=result.get("missing_keywords", []),
        improvements=result.get("improvements", []),
        optimized_text=result.get("optimized_text", ""),
        uses_this_month=uses_this_month,
        uses_remaining=uses_remaining,
        resume_id=resume_id,
    )


# ── Upload endpoint ────────────────────────────────────────────────────────────

@router.post("/upload", response_model=AnalyzeResponse)
async def upload_resume(
    request: Request,
    resume_file: UploadFile = File(...),
    job_description: str = Form(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = resume_file.filename.split('.')[-1].lower()
    if ext not in ['pdf', 'docx', 'doc']:
        raise HTTPException(status_code=422, detail="Only PDF or DOCX files are supported.")

    file_bytes = await resume_file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="File must be under 5MB.")

    if ext == 'pdf':
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        resume_text = "".join(page.extract_text() or "" for page in reader.pages).strip()
    else:
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            resume_text = "\n".join([p.text for p in doc.paragraphs])
        except Exception:
            resume_text = file_bytes.decode('utf-8', errors='ignore')

    if len(resume_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Could not extract enough text. Please paste your resume text instead.")

    uses_this_month, uses_remaining = await check_and_increment_usage(current_user, db)
    result = await run_ai(resume_text, job_description)

    resume_id = await save_resume(
        db=db,
        user_id=current_user.id,
        original_text=resume_text,
        job_description=job_description,
        ats_score=int(result.get("ats_score", 0)),
        missing_keywords=result.get("missing_keywords", []),
        improvements=result.get("improvements", []),
        optimized_text=result.get("optimized_text", ""),
        original_filename=resume_file.filename,
        file_format=ext if ext in ['pdf', 'docx'] else 'txt',
    )

    return AnalyzeResponse(
        ats_score=int(result.get("ats_score", 0)),
        missing_keywords=result.get("missing_keywords", []),
        improvements=result.get("improvements", []),
        optimized_text=result.get("optimized_text", ""),
        uses_this_month=uses_this_month,
        uses_remaining=uses_remaining,
        resume_id=resume_id,
    )