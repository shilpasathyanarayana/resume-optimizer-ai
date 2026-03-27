from typing import Optional
from pydantic import BaseModel, Field


# ── Request bodies ────────────────────────────────────────────────────────────

class GenerateFromDescriptionIn(BaseModel):
    description: str = Field(..., min_length=20, description="Full job description text")


class DirectReviewIn(BaseModel):
    question: str = Field(..., min_length=5)
    answer:   str = Field(..., min_length=1)


# ── Response bodies ───────────────────────────────────────────────────────────

class InterviewQuestionOut(BaseModel):
    id:          int
    question:    str
    user_answer: Optional[str] = None
    ai_feedback: Optional[str] = None
    order_index: int = 0

    class Config:
        from_attributes = True


class FeedbackOut(BaseModel):
    ai_feedback: str