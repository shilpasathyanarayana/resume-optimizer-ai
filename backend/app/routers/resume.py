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

router = APIRouter(prefix="/api/resume", tags=["resume"])

FREE_MONTHLY_LIMIT = 5
PRO_MONTHLY_LIMIT = 999999  # unlimited effectively

security = HTTPBearer()

# ── Schemas ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    resume_text: str
    job_description: str

class AnalyzeResponse(BaseModel):
    ats_score: int
    missing_keywords: list[str]
    improvements: list[str]
    optimized_text: str
    uses_this_month: int
    uses_remaining: int

# ── Auth Helper ────────────────────────────────────────────────────────────────

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
    """Check monthly limit, reset if new month, increment count."""
    now = datetime.utcnow()
    reset_at = user.usage_reset_at

    # Reset counter if it's been more than 30 days
    if (now - reset_at) > timedelta(days=30):
        await db.execute(
            text("UPDATE users SET monthly_usage = 0, usage_reset_at = :now WHERE id = :id"),
            {"now": now, "id": user.id}
        )
        await db.commit()
        monthly_usage = 0
    else:
        monthly_usage = user.monthly_usage

    # Check limit based on plan
    limit = FREE_MONTHLY_LIMIT if user.plan == 'free' else PRO_MONTHLY_LIMIT

    if monthly_usage >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {limit} free optimizations this month. Upgrade to Pro for unlimited access."
        )

    # Increment
    await db.execute(
        text("UPDATE users SET monthly_usage = monthly_usage + 1 WHERE id = :id"),
        {"id": user.id}
    )
    await db.commit()

    return monthly_usage + 1, max(limit - (monthly_usage + 1), 0)

# ── Prompt ─────────────────────────────────────────────────────────────────────

def build_prompt(resume_text: str, job_description: str) -> str:
    return f"""You are an expert resume consultant and ATS optimization specialist.
Analyze the resume against the job description and return ONLY a valid JSON object.
No markdown fences, no explanation — just the raw JSON.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Return this exact JSON structure:
{{
  "ats_score": <integer 0-100>,
  "missing_keywords": ["keyword1", "keyword2"],
  "improvements": ["specific suggestion 1", "specific suggestion 2"],
  "optimized_text": "<full rewritten resume tailored to the role>"
}}

Rules:
- ats_score honestly reflects keyword match and formatting quality
- missing_keywords are the most impactful absent skills/terms from the job description
- improvements are specific and actionable (4-6 items)
- optimized_text is a complete, ready-to-use resume — do NOT truncate it
- Never invent experience or credentials the candidate doesn't have"""

# ── AI Call ────────────────────────────────────────────────────────────────────

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
        raise HTTPException(status_code=502, detail="AI returned an unexpected response. Please try again.")

# ── Usage Status Endpoint ──────────────────────────────────────────────────────

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

    return AnalyzeResponse(
        ats_score=int(result.get("ats_score", 0)),
        missing_keywords=result.get("missing_keywords", []),
        improvements=result.get("improvements", []),
        optimized_text=result.get("optimized_text", ""),
        uses_this_month=uses_this_month,
        uses_remaining=uses_remaining,
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

    return AnalyzeResponse(
        ats_score=int(result.get("ats_score", 0)),
        missing_keywords=result.get("missing_keywords", []),
        improvements=result.get("improvements", []),
        optimized_text=result.get("optimized_text", ""),
        uses_this_month=uses_this_month,
        uses_remaining=uses_remaining,
    )