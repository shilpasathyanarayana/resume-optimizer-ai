from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name must not be empty.")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    email: EmailStr


# ── Login ─────────────────────────────────────────────────────────────────────
# FastAPI OAuth2PasswordRequestForm handles the form fields (username/password).
# We return the same shape the frontend expects.

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    email: EmailStr


# ── Current user (decoded from JWT) ──────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str          # user email
    user_id: int
    name: str
    exp: Optional[datetime] = None


class CurrentUser(BaseModel):
    id: int
    name: str
    email: EmailStr
    plan: str
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True

 
class UpdateProfileRequest(BaseModel):
    name:             Optional[str]      = None
    email:            Optional[EmailStr] = None
    current_password: Optional[str]      = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v
 