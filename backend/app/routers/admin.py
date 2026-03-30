"""
routers/admin.py
Exposes:
  GET  /api/admin/users   – paginated list of all users + subscription data (admin only)

Admin access is controlled by the ADMIN_EMAILS list in config.py (or .env).
No separate is_admin column needed — just add emails to the env var.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.admin import AdminUserRow, AdminUsersResponse
from app.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Admin guard ───────────────────────────────────────────────────────────────

def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    Blocks anyone whose email is not in settings.ADMIN_EMAILS.
    Add to .env:  ADMIN_EMAILS=you@example.com,other@example.com
    """
    allowed: list[str] = [
        e.strip().lower()
        for e in getattr(settings, "ADMIN_EMAILS", "").split(",")
        if e.strip()
    ]
    if current_user.email.lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


# ── GET /api/admin/users ──────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=AdminUsersResponse,
    summary="List all users with subscription data",
)
async def list_users(
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0,    ge=0,   description="Offset for pagination"),
    limit: int = Query(default=200, ge=1,  le=500, description="Max rows to return"),
):
    """
    Returns every user joined with their latest subscription row.
    Subscription columns are NULL when the user has no subscription record.

    The frontend receives a flat object per user — no nesting needed.
    """

    # ── Total count ───────────────────────────────────────────────
    count_result = await db.execute(text("SELECT COUNT(*) FROM users"))
    total: int = count_result.scalar_one()

    # ── Main query: users LEFT JOIN subscriptions ─────────────────
    # We use a LEFT JOIN so users without a subscriptions row still appear.
    # The subquery picks the single most-recent subscription per user.
    rows_result = await db.execute(
        text("""
            SELECT
                u.id,
                u.name,
                u.email,
                u.is_active,
                u.is_verified,
                u.monthly_usage,
                u.created_at,

                COALESCE(s.is_pro, 0)                  AS is_pro,
                COALESCE(s.plan,   'free')              AS subscription_plan,
                COALESCE(s.status, 'inactive')          AS subscription_status,
                s.current_period_end,
                COALESCE(s.cancel_at_period_end, 0)    AS cancel_at_period_end

            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.id

            ORDER BY u.created_at DESC
            LIMIT  :limit
            OFFSET :skip
        """),
        {"limit": limit, "skip": skip},
    )
    rows = rows_result.mappings().all()

    users = [
        AdminUserRow(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            is_active=bool(row["is_active"]),
            is_verified=bool(row["is_verified"]),
            monthly_usage=row["monthly_usage"] or 0,
            created_at=row["created_at"],
            is_pro=bool(row["is_pro"]),
            subscription_plan=row["subscription_plan"],
            subscription_status=row["subscription_status"],
            current_period_end=row["current_period_end"],
            cancel_at_period_end=bool(row["cancel_at_period_end"]),
        )
        for row in rows
    ]

    return AdminUsersResponse(total=total, users=users)