from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os

from database import get_db
from models.user import User, UserLoginLog
from schemas.auth import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
    TokenData, UserMeResponse
)
from services.email_service import send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])

# ── CONFIG ────────────────────────────────────────────────────
SECRET_KEY  = os.getenv("SECRET_KEY", "changeme")
ALGORITHM   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── HELPERS ───────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_verification_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode({"sub": email, "exp": expire, "type": "verify"}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── CURRENT USER DEPENDENCY ──────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("user_id")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def require_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    user = await get_current_user(token, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


# ── REGISTER ─────────────────────────────────────────────────
@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    # Create user
    new_user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        is_active=True,
        is_verified=False,
    )
    db.add(new_user)
    await db.flush()  # get the ID without committing

    # Send verification email
    verify_token = create_verification_token(body.email)
    try:
        send_verification_email(body.email, body.name, verify_token)
    except Exception as e:
        print(f"[register] Email send failed: {e}")
        # Don't block registration if email fails — log and continue

    await db.commit()

    return RegisterResponse(
        message="Account created! Please check your email to verify your account.",
        email=body.email
    )


# ── LOGIN ─────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    # Find user
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Log helper
    async def log_attempt(status: str, reason: str = None):
        log = UserLoginLog(
            user_id=user.id if user else None,
            email=body.email,
            ip_address=ip,
            user_agent=user_agent[:500] if user_agent else None,
            status=status,
            fail_reason=reason
        )
        db.add(log)
        await db.commit()

    # User not found
    if not user:
        await log_attempt("failed", "user_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Wrong password
    if not verify_password(body.password, user.password_hash):
        await log_attempt("failed", "wrong_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Not verified
    if not user.is_verified:
        await log_attempt("failed", "not_verified")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox."
        )

    # Not active
    if not user.is_active:
        await log_attempt("failed", "account_disabled")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled."
        )

    # Success — create token
    token = create_access_token({"user_id": user.id, "email": user.email})
    await log_attempt("success")

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        name=user.name,
        email=user.email,
        plan=user.plan.value
    )


# ── VERIFY EMAIL ──────────────────────────────────────────────
@router.get("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    payload = decode_token(token)

    if not payload or payload.get("type") != "verify":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link."
        )

    email = payload.get("sub")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.is_verified:
        return {"message": "Email already verified. You can log in."}

    user.is_verified = True
    await db.commit()

    return {"message": "Email verified successfully! You can now log in."}


# ── GET CURRENT USER (/me) ────────────────────────────────────
@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user: User = Depends(require_current_user)):
    return current_user
