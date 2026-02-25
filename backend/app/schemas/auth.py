from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


# ── REGISTER ──────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:     str
    email:    EmailStr
    password: str

    @field_validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class RegisterResponse(BaseModel):
    message: str
    email:   str


# ── LOGIN ──────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    name:         str
    email:        str
    plan:         str


# ── TOKEN ──────────────────────────────────────────────────────
class TokenData(BaseModel):
    user_id: Optional[int] = None
    email:   Optional[str] = None


# ── ME ─────────────────────────────────────────────────────────
class UserMeResponse(BaseModel):
    id:          int
    name:        str
    email:       str
    plan:        str
    is_verified: bool

    class Config:
        from_attributes = True
