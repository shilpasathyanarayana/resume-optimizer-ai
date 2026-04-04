"""
main.py          ← starts the app, registers all routes
    ↓
routers/auth.py  ← defines the URL endpoints (/register, /login)
    ↓
services/auth_service.py  ← business logic (hashing, JWT, DB queries)
    ↓
models/user.py   ← defines what the database table looks like
    ↓
database.py      ← manages the DB connection
    ↓
config.py        ← reads settings from .env file
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base
from app.routers.auth import router as auth_router
from app.routers.resume import router as resume_router
from app.routers.payment import router as payment_router
from app.routers.job_tracker import router as job_tracker_router
from app.routers.interview import router as interview_router         # ← NEW
from app.routers.admin import router as admin_router   

import app.models.user       # noqa: F401 – registers ORM models with SQLAlchemy
import app.models.interview  # noqa: F401 – registers InterviewQuestion model   ← NEW


# ── Lifespan: create tables on startup ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    max_retries = 10
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("✅ Database connected and tables created.")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⏳ DB not ready, retrying in 3s... ({attempt + 1}/{max_retries})")
                await asyncio.sleep(3)
            else:
                print(f"❌ Could not connect to DB after {max_retries} attempts: {e}")
                raise
    yield
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ResumeAI API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Global exception handler — always return JSON, never HTML ─────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_ORIGIN,
         "https://resume-optimiser-ai.netlify.app",
    ],
    # REPLACE the full allow_origins list with:
    # allow_origins=[
    #  "https://yourdomain.com",
    #  "https://www.yourdomain.com",
    #  # Only add localhost entries if APP_ENV == 'development'
    # ],
    
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Auth module
app.include_router(auth_router, prefix="/api")

# Resume Optimiser module
app.include_router(resume_router, prefix="/api")

# Payment Gateway module
app.include_router(payment_router, prefix="/api/payments", tags=["payments"])

# Resume Optimiser History module
# app.include_router(resume_history_router, prefix="/api")

# Job Tracker module
app.include_router(job_tracker_router)

# Interview Prep module                                                         ← NEW
# All routes are prefixed /api/interview inside the router itself,
# so no extra prefix is needed here.
app.include_router(interview_router)

# Admin module                                                                  ← NEW
# Prefix is already set inside the router (/api/admin)
app.include_router(admin_router)

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}