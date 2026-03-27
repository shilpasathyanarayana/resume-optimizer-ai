"""
interview_service.py
~~~~~~~~~~~~~~~~~~~~
All Groq API calls for the interview-prep feature.

• generate_questions(description)  → list[str]   (min 5 questions)
• review_answer(question, answer)  → str          (AI feedback paragraph)
"""

import os
import json
import re
from typing import Optional

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # fast & capable

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type":  "application/json",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _groq_chat(messages: list[dict], max_tokens: int = 1500) -> str:
    """Raw Groq chat-completions call. Returns the assistant message text."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set.")

    payload = {
        "model":      GROQ_MODEL,
        "messages":   messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(GROQ_BASE_URL, headers=HEADERS, json=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _extract_json_array(text: str) -> list:
    """
    Robustly pull a JSON array out of a response that may have markdown fences
    or leading prose.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip ```json ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Find first '[' ... ']' block
    start = text.find("[")
    end   = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse a JSON array from Groq response: {text[:400]}")


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_questions(description: str, num_questions: int = 8) -> list[str]:
    """
    Generate interview questions tailored to a job description.
    Returns a list of question strings (min 5, default 8).
    """
    num_questions = max(5, num_questions)

    system_prompt = (
        "You are an expert technical recruiter and career coach. "
        "Your task is to generate targeted interview questions for a candidate "
        "based on a job description. Focus on: role-specific technical skills, "
        "behavioural / situational competencies (use STAR-method prompts), "
        "and a few culture-fit questions. "
        "Return ONLY a valid JSON array of strings — no prose, no markdown fences, "
        "no commentary. Example: [\"Tell me about yourself.\", \"Describe a time...\"]"
    )

    user_prompt = (
        f"Generate exactly {num_questions} interview questions for the following job description.\n\n"
        f"Job Description:\n{description}\n\n"
        f"Return a JSON array of {num_questions} question strings. Nothing else."
    )

    raw = await _groq_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=1200,
    )

    questions = _extract_json_array(raw)

    # Safety: ensure we have at least 5 non-empty strings
    questions = [q.strip() for q in questions if isinstance(q, str) and q.strip()]
    if len(questions) < 5:
        raise ValueError(f"AI returned fewer than 5 questions ({len(questions)}). Raw: {raw[:300]}")

    return questions


async def review_answer(question: str, answer: str) -> str:
    """
    Review a candidate's answer to an interview question and return
    constructive AI feedback as a plain-text paragraph.
    """
    system_prompt = (
        "You are a senior career coach reviewing a job candidate's interview answer. "
        "Provide clear, constructive, and encouraging feedback. "
        "Structure your response as: "
        "1) What they did well, "
        "2) What could be improved (be specific), "
        "3) A brief example of how to strengthen the answer using the STAR method if applicable. "
        "Keep your response concise — 3 to 5 sentences maximum. "
        "Write in plain text; do NOT use markdown, bullet points, or headers."
    )

    user_prompt = (
        f"Interview Question:\n{question}\n\n"
        f"Candidate's Answer:\n{answer}\n\n"
        "Please review this answer and provide feedback."
    )

    feedback = await _groq_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=500,
    )

    return feedback