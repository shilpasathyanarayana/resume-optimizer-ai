from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Enum, ForeignKey
from app.database import Base
from sqlalchemy.sql import func

class Resume(Base):
    __tablename__ = "resumes"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    user_id           = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    original_filename = Column(String(255), nullable=True)
    original_text     = Column(Text, nullable=False)
    job_title         = Column(String(255), nullable=True)
    job_description   = Column(Text, nullable=False)
    ats_score         = Column(Integer, nullable=True)
    missing_keywords  = Column(JSON, nullable=True)
    improvements      = Column(JSON, nullable=True)
    optimized_text    = Column(Text, nullable=True)
    file_format       = Column(
        Enum('pdf', 'docx', 'txt', name='resume_file_format_enum'),
        nullable=True
    )
    status            = Column(
        Enum('pending', 'processing', 'completed', 'failed', name='resume_status_enum'),
        nullable=False,
        default='pending',
        index=True
    )
    error_message     = Column(String(500), nullable=True)
    celery_task_id    = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())