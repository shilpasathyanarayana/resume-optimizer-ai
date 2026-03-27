"""
routers/job_tracker.py
Self-contained — schemas, auth, and all endpoints in one file.
Matches the patterns in routers/resume.py exactly.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from jose import jwt, JWTError

from app.config import settings
from app.database import get_db
from app.routers.auth import require_pro_user  #for blocking free user accessing from pro feature

# every route is built like [prefix] + [route path]
router   = APIRouter(prefix="/api/jobs", tags=["jobs"])
security = HTTPBearer()

DEFAULT_STAGES = [
    {"name": "Applied",             "position": 1},
    {"name": "Interview Scheduled", "position": 2},
    {"name": "Offer",               "position": 3},
    {"name": "Rejected",            "position": 4},
]

# ── Schemas ────────────────────────────────────────────────────────────────────

class StageCreate(BaseModel):
    name:     str
    position: int

class StageUpdate(BaseModel):
    name:     Optional[str] = None
    position: Optional[int] = None

class ApplicationCreate(BaseModel):
    company:         str
    role:            str
    job_url:         Optional[str]      = None
    stage_id:        int
    applied_at:      Optional[datetime] = None
    next_action:     Optional[str]      = None
    next_action_due: Optional[datetime] = None
    notes:           Optional[str]      = None

class ApplicationUpdate(BaseModel):
    company:         Optional[str]      = None
    role:            Optional[str]      = None
    job_url:         Optional[str]      = None
    stage_id:        Optional[int]      = None
    applied_at:      Optional[datetime] = None
    next_action:     Optional[str]      = None
    next_action_due: Optional[datetime] = None
    notes:           Optional[str]      = None

class MoveApplication(BaseModel):
    stage_id: int

# ── Auth (same pattern as resume.py) ──────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub     = payload.get("sub")
        user_id = payload.get("user_id")
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please log in again.")

    result = await db.execute(
        text("SELECT id, name, email FROM users WHERE (id = :user_id OR email = :email) AND is_active = 1"),
        {"user_id": user_id, "email": sub}
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

# ── Stage helpers ──────────────────────────────────────────────────────────────

async def get_or_create_default_stages(db: AsyncSession, user_id: int):
    result = await db.execute(
        text("SELECT id, name, position, is_default, created_at FROM job_stages WHERE user_id = :uid ORDER BY position"),
        {"uid": user_id}
    )
    rows = result.fetchall()
    if rows:
        return rows

    # First visit — seed default stages
    for s in DEFAULT_STAGES:
        await db.execute(
            text("INSERT INTO job_stages (user_id, name, position, is_default) VALUES (:uid, :name, :pos, 1)"),
            {"uid": user_id, "name": s["name"], "pos": s["position"]}
        )
    await db.commit()

    result = await db.execute(
        text("SELECT id, name, position, is_default, created_at FROM job_stages WHERE user_id = :uid ORDER BY position"),
        {"uid": user_id}
    )
    return result.fetchall()

# ── BOARD ──────────────────────────────────────────────────────────────────────

# with prefix the complete api end point is /api/jobs/board
@router.get("/board")
async def get_kanban_board(
    user=Depends(require_pro_user),  # ← enforce Pro plan
    db: AsyncSession = Depends(get_db),
):
    stages = await get_or_create_default_stages(db, user.id)

    result = await db.execute(
        text("""
            SELECT a.id, a.company, a.role, a.job_url, a.stage_id,
                   s.name as stage_name,
                   a.applied_at, a.next_action, a.next_action_due,
                   a.notes, a.created_at, a.updated_at
            FROM job_applications a
            JOIN job_stages s ON s.id = a.stage_id
            WHERE a.user_id = :uid
            ORDER BY a.created_at DESC
        """),
        {"uid": user.id}
    )
    applications = result.fetchall()

    # Group applications by stage
    stage_map = {s.id: {"stage": dict(s._mapping), "applications": []} for s in stages}
    for app in applications:
        if app.stage_id in stage_map:
            stage_map[app.stage_id]["applications"].append(dict(app._mapping))

    return {"columns": list(stage_map.values())}

# ── STAGES ─────────────────────────────────────────────────────────────────────

@router.get("/stages")
async def list_stages(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await get_or_create_default_stages(db, user.id)
    return [dict(r._mapping) for r in rows]


@router.post("/stages", status_code=201)
async def add_stage(
    body: StageCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("INSERT INTO job_stages (user_id, name, position, is_default) VALUES (:uid, :name, :pos, 0)"),
        {"uid": user.id, "name": body.name, "pos": body.position}
    )
    await db.commit()
    return {"id": result.lastrowid, "message": "Stage created."}


@router.patch("/stages/{stage_id}")
async def edit_stage(
    stage_id: int,
    body: StageUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.name:
        await db.execute(
            text("UPDATE job_stages SET name = :name WHERE id = :id AND user_id = :uid"),
            {"name": body.name, "id": stage_id, "uid": user.id}
        )
    if body.position is not None:
        await db.execute(
            text("UPDATE job_stages SET position = :pos WHERE id = :id AND user_id = :uid"),
            {"pos": body.position, "id": stage_id, "uid": user.id}
        )
    await db.commit()
    return {"message": "Stage updated."}


@router.delete("/stages/{stage_id}")
async def remove_stage(
    stage_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Block delete if applications exist in this stage
    result = await db.execute(
        text("SELECT COUNT(*) as cnt FROM job_applications WHERE stage_id = :sid AND user_id = :uid"),
        {"sid": stage_id, "uid": user.id}
    )
    if result.fetchone().cnt > 0:
        raise HTTPException(status_code=409, detail="Move or delete applications in this stage first.")

    await db.execute(
        text("DELETE FROM job_stages WHERE id = :id AND user_id = :uid"),
        {"id": stage_id, "uid": user.id}
    )
    await db.commit()
    return {"message": "Stage deleted."}

# ── APPLICATIONS ───────────────────────────────────────────────────────────────

@router.post("/applications", status_code=201)
async def add_application(
    body: ApplicationCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.company.strip():
        raise HTTPException(status_code=422, detail="Company name is required.")
    if not body.role.strip():
        raise HTTPException(status_code=422, detail="Role is required.")

    result = await db.execute(
        text("""
            INSERT INTO job_applications
                (user_id, company, role, job_url, stage_id,
                 applied_at, next_action, next_action_due, notes)
            VALUES
                (:uid, :company, :role, :job_url, :stage_id,
                 :applied_at, :next_action, :next_action_due, :notes)
        """),
        {
            "uid":             user.id,
            "company":         body.company,
            "role":            body.role,
            "job_url":         body.job_url,
            "stage_id":        body.stage_id,
            "applied_at":      body.applied_at,
            "next_action":     body.next_action,
            "next_action_due": body.next_action_due,
            "notes":           body.notes,
        }
    )
    await db.commit()
    return {"id": result.lastrowid, "message": "Application added."}


@router.patch("/applications/{app_id}")
async def edit_application(
    app_id: int,
    body: ApplicationUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data   = body.model_dump(exclude_none=True)
    fields = [f"{col} = :{col}" for col in data]
    if not fields:
        raise HTTPException(status_code=422, detail="Nothing to update.")

    params = {**data, "id": app_id, "uid": user.id}
    await db.execute(
        text(f"UPDATE job_applications SET {', '.join(fields)} WHERE id = :id AND user_id = :uid"),
        params
    )
    await db.commit()
    return {"message": "Application updated."}


@router.patch("/applications/{app_id}/move")
async def move_application(
    app_id: int,
    body: MoveApplication,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("UPDATE job_applications SET stage_id = :stage_id WHERE id = :id AND user_id = :uid"),
        {"stage_id": body.stage_id, "id": app_id, "uid": user.id}
    )
    await db.commit()
    return {"message": "Application moved."}


@router.delete("/applications/{app_id}")
async def remove_application(
    app_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("DELETE FROM job_applications WHERE id = :id AND user_id = :uid"),
        {"id": app_id, "uid": user.id}
    )
    await db.commit()
    return {"message": "Application deleted."}
