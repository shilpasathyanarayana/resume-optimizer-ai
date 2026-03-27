"""
routers/interview.py
~~~~~~~~~~~~~~~~~~~~
Endpoints for interviewPrep.html (paste-only mode — no job tracker needed)

POST /api/interview/generate-from-description   → generate questions from pasted JD
POST /api/interview/review-answer               → get AI feedback on a single answer
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.schemas.interview import (
    GenerateFromDescriptionIn,
    DirectReviewIn,
    InterviewQuestionOut,
    FeedbackOut,
)
from app.services.interview_service import generate_questions, review_answer
from typing import List

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/generate-from-description", response_model=List[InterviewQuestionOut])
async def generate_from_description(
    body:         GenerateFromDescriptionIn,
    current_user: User = Depends(get_current_user),
):
    """
    Generate tailored interview questions from a pasted job description.
    Stateless — nothing is saved to the database.
    """
    try:
        question_texts = await generate_questions(body.description)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    return [
        InterviewQuestionOut(id=0, question=q, order_index=i)
        for i, q in enumerate(question_texts)
    ]


@router.post("/review-answer", response_model=FeedbackOut)
async def review_answer_direct(
    body:         DirectReviewIn,
    current_user: User = Depends(get_current_user),
):
    """
    Get AI feedback on a candidate's answer.
    Stateless — takes question + answer directly, nothing saved to DB.
    """
    try:
        feedback = await review_answer(body.question, body.answer)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI review failed: {exc}")

    return FeedbackOut(ai_feedback=feedback)