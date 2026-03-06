"""
routers/auth.py
Exposes:
  POST /api/auth/register  – create account, return JWT
  POST /api/auth/login     – OAuth2 password flow, return JWT
  GET  /api/auth/me        – return current user profile (protected)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user = await get_user_by_email(db, payload.sub)
    if user is None or not user.is_active:
        raise credentials_exception

    return CurrentUser.model_validate(user)


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
    # Check for duplicate email
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

    # User not found
    if user is None:
        await write_login_log(
            db, email=email, status="failed",
            ip_address=ip, user_agent=ua, fail_reason="user_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Wrong password
    if not verify_password(form.password, user.password_hash):
        await write_login_log(
            db, email=email, status="failed", user_id=user.id,
            ip_address=ip, user_agent=ua, fail_reason="wrong_password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Inactive account
    if not user.is_active:
        await write_login_log(
            db, email=email, status="blocked", user_id=user.id,
            ip_address=ip, user_agent=ua, fail_reason="account_inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )

    # Success
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
    return current_user
