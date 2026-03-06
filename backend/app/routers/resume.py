import json
import io
import PyPDF2
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.database import get_db
from jose import jwt, JWTError
from typing import List, Optional

router = APIRouter(prefix="/api/resume", tags=["resume"])

FREE_MONTHLY_LIMIT = 5
PRO_MONTHLY_LIMIT = 999999

security = HTTPBearer()

# ── Schemas ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    resume_text: str
    job_description: str

class AnalyzeResponse(BaseModel):
    ats_score: int
    missing_keywords: List[str]
    improvements: List[str]
    optimized_text: str
    uses_this_month: int
    uses_remaining: int
    resume_id: Optional[int] = None

# ── Auth ───────────────────────────────────────────────────────────────────────

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
        text("SELECT id, name, email, plan, monthly_usage, usage_reset_at FROM users WHERE (id = :user_id OR email = :email) AND is_active = 1"),
        {"user_id": user_id, "email": sub}
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

# ── Usage Helpers ──────────────────────────────────────────────────────────────

async def check_and_increment_usage(user, db: AsyncSession):
    now = datetime.utcnow()
    reset_at = user.usage_reset_at
    monthly_usage = user.monthly_usage

    if (now - reset_at) > timedelta(days=30):
        monthly_usage = 0
        await db.execute(
            text("UPDATE users SET monthly_usage = 0, usage_reset_at = :now WHERE id = :id"),
            {"now": now, "id": user.id}
        )

    limit = FREE_MONTHLY_LIMIT if user.plan == 'free' else PRO_MONTHLY_LIMIT

    if monthly_usage >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {limit} free optimizations this month. Upgrade to Pro for unlimited access."
        )

    new_usage = monthly_usage + 1
    await db.execute(
        text("UPDATE users SET monthly_usage = monthly_usage + 1 WHERE id = :id"),
        {"id": user.id}
    )
    await db.commit()

    return new_usage, max(limit - new_usage, 0)

# ── Save Resume ────────────────────────────────────────────────────────────────

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
            "user_id": user_id,
            "original_filename": original_filename,
            "original_text": original_text,
            "job_title": job_title,
            "job_description": job_description,
            "ats_score": ats_score,
            "missing_keywords": json.dumps(missing_keywords),
            "improvements": json.dumps(improvements),
            "optimized_text": optimized_text,
            "file_format": file_format,
        }
    )
    await db.commit()
    return result.lastrowid

# ── Usage Endpoint ─────────────────────────────────────────────────────────────

@router.get("/usage")
async def get_usage(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.utcnow()
    monthly_usage = user.monthly_usage
    if (now - user.usage_reset_at) > timedelta(days=30):
        monthly_usage = 0

    limit = FREE_MONTHLY_LIMIT if user.plan == 'free' else PRO_MONTHLY_LIMIT
    return {
        "plan": user.plan,
        "uses_this_month": monthly_usage,
        "uses_remaining": max(limit - monthly_usage, 0),
        "limit": limit,
        "resets_at": (user.usage_reset_at + timedelta(days=30)).isoformat()
    }

# ── AI Service ─────────────────────────────────────────────────────────────────

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
                {
                    "role": "system",
                    "content": "You are an expert resume consultant. Always respond with valid JSON only — no markdown, no explanation."
                },
                {
                    "role": "user",
                    "content": build_prompt(resume_text, job_description)
                }
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

# ── Analyze Endpoint ───────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_resume(
    body: AnalyzeRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if len(body.resume_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Resume text is too short.")
    if len(body.job_description.strip()) < 50:
        raise HTTPException(status_code=422, detail="Job description is too short.")

    uses_this_month, uses_remaining = await check_and_increment_usage(user, db)
    result = await run_ai(body.resume_text, body.job_description)

    resume_id = await save_resume(
        db=db,
        user_id=user.id,
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

# ── Upload Endpoint ────────────────────────────────────────────────────────────

@router.post("/upload", response_model=AnalyzeResponse)
async def upload_resume(
    request: Request,
    resume_file: UploadFile = File(...),
    job_description: str = Form(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
        raise HTTPException(status_code=422, detail="Could not extract enough text from the file. Please paste your resume text instead.")

    uses_this_month, uses_remaining = await check_and_increment_usage(user, db)
    result = await run_ai(resume_text, job_description)

    resume_id = await save_resume(
        db=db,
        user_id=user.id,
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
