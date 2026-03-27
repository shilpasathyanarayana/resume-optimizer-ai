from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base


class InterviewQuestion(Base):
    """
    Stores AI-generated interview questions linked to a job application.
    Questions are regenerated on demand; old ones are deleted first.
    """
    __tablename__ = "interview_questions"

    id            = Column(Integer, primary_key=True, index=True)
    job_id        = Column(Integer, ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question      = Column(Text, nullable=False)
    user_answer   = Column(Text, nullable=True)
    ai_feedback   = Column(Text, nullable=True)
    order_index   = Column(Integer, default=0)          # keeps original order
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships (read-only; FK tables are owned by other routers)
    # job  = relationship("JobApplication", back_populates="interview_questions")
    # user = relationship("User")