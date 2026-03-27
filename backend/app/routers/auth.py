"""
routers/auth.py
Exposes:
  POST /api/auth/register       – create account, return JWT
  POST /api/auth/login          – OAuth2 password flow, return JWT
  GET  /api/auth/me             – return current user profile (protected)
  PATCH /api/auth/update-profile
  POST  /api/auth/change-password
  DELETE /api/auth/delete-account
  GET  /api/auth/job-profile
  PATCH /api/auth/update-job-profile
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginResponse,
    CurrentUser,
)
from app.services.auth_service import (
    get_user_by_email,
    create_user,
    verify_password,
    create_access_token,
    decode_access_token,
    write_login_log,
    hash_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── helpers ───────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # ✅ Signature is verified here using SECRET_KEY.
    # A tampered JWT (e.g. forged is_pro claim) will fail with JWTError → 401.
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user = await get_user_by_email(db, payload.sub)
    if user is None or not user.is_active:
        raise credentials_exception

    # ✅ is_pro is read from the subscriptions table — the JWT claim is ignored.
    # This means no client-side manipulation of localStorage can grant Pro access.
    plan_result = await db.execute(
        text("SELECT is_pro FROM subscriptions WHERE user_id = :id ORDER BY created_at DESC LIMIT 1"),
        {"id": user.id}
    )
    plan_row = plan_result.fetchone()
    is_pro = bool(plan_row.is_pro) if plan_row else False

    # ✅ Construct CurrentUser directly — do NOT use model_validate(user)
    # which would discard the DB-sourced is_pro we just fetched.
    return CurrentUser(
        id=user.id,
        name=user.name,
        email=user.email,
        is_pro=is_pro,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


# ✅ PROTECTION DEPENDENCY — use this on any Pro-only endpoint
def require_pro_user(current_user: CurrentUser = Depends(get_current_user)):
    if not current_user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pro subscription required."
        )
    return current_user


@router.get("/pro-only-data")
async def get_pro_data(current_user: CurrentUser = Depends(require_pro_user)):
    return {"secret": "This is only for Pro users"}


# ── REGISTER ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    try:
        user = await create_user(db, name=body.name, email=body.email, password=body.password)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    token = create_access_token(user)
    return RegisterResponse(access_token=token, name=user.name, email=user.email)


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login with email + password (OAuth2 form)",
)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")[:500]
    email = form.username.lower().strip()

    user = await get_user_by_email(db, email)

    if user is None:
        await write_login_log(
            db, email=email, status="failed",
            ip_address=ip, user_agent=ua, fail_reason="user_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(form.password, user.password_hash):
        await write_login_log(
            db, email=email, status="failed", user_id=user.id,
            ip_address=ip, user_agent=ua, fail_reason="wrong_password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        await write_login_log(
            db, email=email, status="blocked", user_id=user.id,
            ip_address=ip, user_agent=ua, fail_reason="account_inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )

    await write_login_log(
        db, email=email, status="success", user_id=user.id,
        ip_address=ip, user_agent=ua,
    )

    token = create_access_token(user)
    return LoginResponse(access_token=token, name=user.name, email=user.email)


# ── ME (protected) ────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=CurrentUser,
    summary="Return the currently logged-in user",
)
async def me(current_user: CurrentUser = Depends(get_current_user)):
    # ✅ is_pro in this response comes from the DB (via get_current_user),
    # so the frontend can trust it — no JWT payload reading needed client-side.
    return current_user


# ── UPDATE PROFILE ────────────────────────────────────────────────────────────

@router.patch(
    "/update-profile",
    summary="Update name or email",
)
async def update_profile(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()

    new_name  = (body.get("name")  or "").strip() or None
    new_email = (body.get("email") or "").strip() or None
    password  = body.get("current_password")

    if not new_name and not new_email:
        raise HTTPException(status_code=422, detail="Nothing to update.")

    result = await db.execute(
        text("SELECT id, name, email, password_hash FROM users WHERE id = :id"),
        {"id": current_user.id}
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if new_name:
        if len(new_name) < 2:
            raise HTTPException(status_code=422, detail="Name must be at least 2 characters.")
        await db.execute(
            text("UPDATE users SET name = :name WHERE id = :id"),
            {"name": new_name, "id": current_user.id}
        )
        await db.commit()
        return {"message": "Name updated successfully.", "name": new_name}

    if new_email:
        if not password:
            raise HTTPException(status_code=422, detail="Current password is required to change email.")
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect password.")

        existing = await db.execute(
            text("SELECT id FROM users WHERE email = :email AND id != :id"),
            {"email": new_email, "id": current_user.id}
        )
        if existing.fetchone():
            raise HTTPException(status_code=409, detail="This email is already in use.")

        await db.execute(
            text("UPDATE users SET email = :email WHERE id = :id"),
            {"email": new_email, "id": current_user.id}
        )
        await db.commit()
        return {"message": "Email updated successfully.", "email": new_email}


# ── CHANGE PASSWORD ───────────────────────────────────────────────────────────

@router.post(
    "/change-password",
    summary="Change password — requires current password",
)
async def change_password(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()

    current_pw = body.get("current_password", "")
    new_pw     = body.get("new_password", "")

    if not current_pw:
        raise HTTPException(status_code=422, detail="Current password is required.")
    if not new_pw or len(new_pw) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")
    if current_pw == new_pw:
        raise HTTPException(status_code=422, detail="New password must be different from current password.")

    result = await db.execute(
        text("SELECT password_hash FROM users WHERE id = :id"),
        {"id": current_user.id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")

    if not verify_password(current_pw, row.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect current password.")

    new_hash = hash_password(new_pw)
    await db.execute(
        text("UPDATE users SET password_hash = :hash WHERE id = :id"),
        {"hash": new_hash, "id": current_user.id}
    )
    await db.commit()
    return {"message": "Password changed successfully."}


# ── DELETE ACCOUNT ────────────────────────────────────────────────────────────

@router.delete(
    "/delete-account",
    summary="Permanently delete account and all associated data",
)
async def delete_account(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.id

    await db.execute(text("DELETE FROM resumes            WHERE user_id = :id"), {"id": user_id})
    await db.execute(text("DELETE FROM user_login_log     WHERE user_id = :id"), {"id": user_id})
    await db.execute(text("DELETE FROM subscriptions      WHERE user_id = :id"), {"id": user_id})
    await db.execute(text("DELETE FROM job_applications   WHERE user_id = :id"), {"id": user_id})
    await db.execute(text("DELETE FROM job_stages         WHERE user_id = :id"), {"id": user_id})
    await db.execute(text("DELETE FROM users              WHERE id      = :id"), {"id": user_id})
    await db.commit()

    return {"message": "Account deleted successfully."}


# ── GET JOB PROFILE ───────────────────────────────────────────────────────────

@router.get("/job-profile")
async def get_job_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("SELECT job_title, experience_level, location FROM user_profiles WHERE user_id = :uid"),
        {"uid": current_user.id}
    )
    row = result.fetchone()
    if not row:
        return {"job_title": None, "experience_level": None, "location": None}
    return {"job_title": row.job_title, "experience_level": row.experience_level, "location": row.location}


# ── UPDATE JOB PROFILE ────────────────────────────────────────────────────────

@router.patch("/update-job-profile")
async def update_job_profile(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()

    job_title        = body.get("job_title") or body.get("JobTitle")
    experience_level = body.get("experience_level")
    location         = body.get("location")

    if not any([job_title, experience_level, location]):
        raise HTTPException(status_code=422, detail="Nothing to update.")

    valid_levels = {"student", "fresher", "junior", "intermediate", "senior"}
    if experience_level and experience_level not in valid_levels:
        raise HTTPException(
            status_code=422,
            detail=f"experience_level must be one of: {', '.join(valid_levels)}"
        )

    result = await db.execute(
        text("SELECT id FROM user_profiles WHERE user_id = :uid"),
        {"uid": current_user.id}
    )
    exists = result.fetchone()

    if exists:
        fields, params = [], {"uid": current_user.id}
        if job_title:        fields.append("job_title = :job_title");               params["job_title"]        = job_title
        if experience_level: fields.append("experience_level = :experience_level"); params["experience_level"] = experience_level
        if location:         fields.append("location = :location");                 params["location"]         = location

        await db.execute(
            text(f"UPDATE user_profiles SET {', '.join(fields)} WHERE user_id = :uid"),
            params
        )
    else:
        await db.execute(
            text("""
                INSERT INTO user_profiles (user_id, job_title, experience_level, location)
                VALUES (:uid, :job_title, :experience_level, :location)
            """),
            {
                "uid":              current_user.id,
                "job_title":        job_title,
                "experience_level": experience_level,
                "location":         location,
            }
        )

    await db.commit()
    return {"message": "Profile updated successfully."}