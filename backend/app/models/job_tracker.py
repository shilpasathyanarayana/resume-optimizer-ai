from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base


class JobStage(Base):
    __tablename__ = "job_stages"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name       = Column(String(100), nullable=False)
    position   = Column(Integer, nullable=False)
    is_default = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("JobApplication", back_populates="stage")


class JobApplication(Base):
    __tablename__ = "job_applications"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company         = Column(String(255), nullable=False)
    role            = Column(String(255), nullable=False)
    job_url         = Column(String(500), nullable=True)
    stage_id        = Column(Integer, ForeignKey("job_stages.id", ondelete="RESTRICT"), nullable=False, index=True)
    description     = Column(Text, nullable=True)
    applied_at      = Column(DateTime, nullable=True)
    next_action     = Column(String(255), nullable=True)
    next_action_due = Column(DateTime, nullable=True)
    notes           = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stage = relationship("JobStage", back_populates="applications")
    interview_questions = relationship("InterviewQuestion", back_populates="job")