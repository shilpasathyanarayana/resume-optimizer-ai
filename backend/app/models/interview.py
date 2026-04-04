from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id                 = Column(Integer, primary_key=True, index=True)
    job_application_id = Column(Integer, ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    question           = Column(Text, nullable=False)
    user_answer        = Column(Text, nullable=True)
    ai_feedback        = Column(Text, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("JobApplication", back_populates="interview_questions")