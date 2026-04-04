"""
schemas/payment.py
==================
Pydantic v2 request / response models for all payment endpoints.
Matches the style of schemas/auth.py in your project.

Changes from v1:
  - CheckoutRequest: added `currency` field ("usd" | "inr")
  - PlanInfo: added `currency` field so frontend knows which symbol to show
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


# ── Checkout ──────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    """POST /api/payments/checkout"""
    plan: str                                    # "pro_monthly" | "pro_yearly"
    currency: Literal["usd", "inr"] = "usd"     # region-based; detected on frontend


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id:   str


# ── Customer Portal ───────────────────────────────────────────────────────────

class PortalResponse(BaseModel):
    portal_url: str


# ── Subscription status (returned to frontend) ────────────────────────────────

class SubscriptionStatusResponse(BaseModel):
    is_pro:               bool
    plan:                 Optional[str]      = None
    status:               Optional[str]      = None
    current_period_end:   Optional[datetime] = None
    cancel_at_period_end: bool               = False

    model_config = {"from_attributes": True}


# ── Plan listing ──────────────────────────────────────────────────────────────

class PlanInfo(BaseModel):
    key:      str
    name:     str
    amount:   int       # cents (USD) or paise (INR)
    currency: str       # "usd" | "inr"
    interval: str
    features: list[str]


class PlansResponse(BaseModel):
    plans: list[PlanInfo]


# ── Stripe public config (publishable key) ────────────────────────────────────

class StripeConfigResponse(BaseModel):
    publishable_key: str