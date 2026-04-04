from sqlalchemy import Column, Integer, String, Enum, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(100), nullable=False)
    email         = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active     = Column(Boolean, nullable=False, default=True)
    is_verified   = Column(Boolean, nullable=False, default=False)
    monthly_usage = Column(Integer, nullable=False, default=0)
    usage_reset_at = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())
    updated_at    = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class UserLoginLog(Base):
    __tablename__ = "user_login_log"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, nullable=True)
    email       = Column(String(255), nullable=False, index=True)
    ip_address  = Column(String(45), nullable=True)
    user_agent  = Column(String(500), nullable=True)
    status      = Column(Enum("success", "failed", "blocked", name="login_status_enum"), nullable=False)  # ← added name
    fail_reason = Column(String(255), nullable=True)
    created_at  = Column(DateTime, nullable=False, server_default=func.now())