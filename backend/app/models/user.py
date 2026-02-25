from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from database import Base
import enum


class PlanEnum(str, enum.Enum):
    free = "free"
    pro  = "pro"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(100), nullable=False)
    email         = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    is_verified   = Column(Boolean, default=False, nullable=False)
    plan          = Column(Enum(PlanEnum), default=PlanEnum.free, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class UserLoginLog(Base):
    __tablename__ = "user_login_log"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, nullable=True)   # NULL if email not found
    email       = Column(String(255), nullable=False, index=True)
    ip_address  = Column(String(45), nullable=True)
    user_agent  = Column(String(500), nullable=True)
    status      = Column(Enum("success", "failed", "blocked", name="login_status"), nullable=False)
    fail_reason = Column(String(255), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
