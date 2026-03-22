"""
schemas/payment.py
==================
Pydantic v2 request / response models for all payment endpoints.
Matches the style of schemas/auth.py in your project.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# ── Checkout ──────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    """POST /api/payments/checkout"""
    plan: str  # "pro_monthly" | "pro_yearly"


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id:   str


# ── Customer Portal ───────────────────────────────────────────────────────────

class PortalResponse(BaseModel):
    portal_url: str


# ── Subscription status (returned to frontend) ────────────────────────────────

class SubscriptionStatusResponse(BaseModel):
    is_pro:               bool
    plan:                 Optional[str]    = None
    status:               Optional[str]    = None
    current_period_end:   Optional[datetime] = None
    cancel_at_period_end: bool             = False

    model_config = {"from_attributes": True}


# ── Plan listing ──────────────────────────────────────────────────────────────

class PlanInfo(BaseModel):
    key:      str
    name:     str
    amount:   int    # cents
    interval: str
    features: list[str]


class PlansResponse(BaseModel):
    plans: list[PlanInfo]


# ── Stripe public config (publishable key) ────────────────────────────────────

class StripeConfigResponse(BaseModel):
    publishable_key: str
