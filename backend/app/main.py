from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from routers.auth import router as auth_router

app = FastAPI(
    title="ResumeAI API",
    description="AI-powered resume optimization backend",
    version="0.1.0"
)

# ── CORS ──────────────────────────────────────────────────────
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTERS ───────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api")

# ── HEALTH CHECK ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}
