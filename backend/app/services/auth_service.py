"""
services/auth_service.py
Handles password hashing, JWT creation/verification, and login-log writes.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserLoginLog
from app.schemas.auth import TokenPayload


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt $2b$ hash of *plain*."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """
    Return True when *plain* matches *hashed*.

    Handles both $2b$ (Python bcrypt) and $2y$ (PHP bcrypt) prefixes —
    they are identical except for the prefix byte, so we normalise before
    comparing.
    """
    try:
        # Normalise PHP-generated $2y$ hashes to $2b$ so Python's bcrypt accepts them
        if hashed.startswith("$2y$"):
            hashed = "$2b$" + hashed[4:]

        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    """Mint a signed JWT for *user*."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user.email,
        "user_id": user.id,
        "name": user.name,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT; return None on any error."""
    try:
        raw = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return TokenPayload(**raw)
    except JWTError:
        return None


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, name: str, email: str, password: str) -> User:
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()  # assigns user.id without committing
    return user


# ── Login log ─────────────────────────────────────────────────────────────────

async def write_login_log(
    db: AsyncSession,
    *,
    email: str,
    status: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    fail_reason: Optional[str] = None,
) -> None:
    log = UserLoginLog(
        user_id=user_id,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        fail_reason=fail_reason,
    )
    db.add(log)
