"""
routers/payment.py
==================
Registered in main.py as:
    app.include_router(payment_router, prefix="/api/payments", tags=["payments"])

Endpoints:
    GET  /api/payments/config     → Stripe publishable key          [public]
    GET  /api/payments/plans      → available plans                 [public]
    POST /api/payments/checkout   → create Stripe checkout session  [JWT required]
    POST /api/payments/portal     → open Stripe customer portal     [JWT required]
    GET  /api/payments/status     → current user's subscription     [JWT required]
    POST /api/payments/webhook    → Stripe webhook receiver         [NO auth — Stripe signs it]
"""

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings

# ── Re-use your existing auth dependency ──────────────────────────────────────
# get_current_user returns CurrentUser (Pydantic schema, not ORM model)
# CurrentUser fields available: id, name, email, plan, is_active, is_verified
from app.routers.auth import get_current_user
from app.schemas.auth import CurrentUser

from app.schemas.payment import (
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    SubscriptionStatusResponse,
    PlansResponse,
    PlanInfo,
    StripeConfigResponse,
)
from app.services.stripe_service import (
    PLANS,
    create_checkout_session,
    create_portal_session,
    get_or_create_subscription,
    construct_webhook_event,
    handle_webhook_event,
)

# No prefix is defined here since the prefix are defained at main.py
router = APIRouter()


# ── 1. Stripe publishable key (public — no auth needed) ───────────────────────

@router.get("/config", response_model=StripeConfigResponse)
async def stripe_config():
    """Returns the publishable key so the frontend can initialise Stripe.js."""
    return StripeConfigResponse(publishable_key=settings.STRIPE_PUBLISHABLE_KEY)


# ── 2. Available plans (public — no auth needed) ──────────────────────────────

@router.get("/plans", response_model=PlansResponse)
async def list_plans():
    """Returns all subscription plans. price_id is intentionally hidden."""
    return PlansResponse(plans=[
        PlanInfo(
            key=key,
            name=p["name"],
            amount=p["amount"],
            interval=p["interval"],
            features=p["features"],
        )
        for key, p in PLANS.items()
    ])


# ── 3. Create checkout session ────────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    current_user: CurrentUser = Depends(get_current_user),  # .id / .email / .plan
):
    """
    Creates a Stripe Checkout session for the logged-in user.
    Frontend receives checkout_url and redirects the browser there.
    No DB session needed here — Stripe stores the state; webhook updates our DB.
    """
    # Prevent double-subscribing if already on Pro
    if current_user.plan == "pro":
        raise HTTPException(
            status_code=400,
            detail="You already have an active Pro subscription.",
        )

    try:
        session = await create_checkout_session(
            plan_key   = body.plan,
            user_id    = current_user.id,
            user_email = current_user.email,
        )
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message}")


# ── 4. Customer portal ────────────────────────────────────────────────────────

@router.post("/portal", response_model=PortalResponse)
async def customer_portal(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Opens the Stripe-hosted portal: user can update card, change plan, cancel.
    Requires a stripe_customer_id stored after their first checkout.
    """
    sub = await get_or_create_subscription(db, current_user.id)

    if not sub.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No billing account found. Please subscribe first.",
        )
    try:
        portal = await create_portal_session(sub.stripe_customer_id)
        return PortalResponse(portal_url=portal.url)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message}")


# ── 5. Subscription status ────────────────────────────────────────────────────

@router.get("/status", response_model=SubscriptionStatusResponse)
async def subscription_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the current user's subscription state directly from our DB.
    Use this to gate Pro features on the frontend / other routers.
    """
    sub = await get_or_create_subscription(db, current_user.id)
    return SubscriptionStatusResponse(
        is_pro               = sub.is_pro,
        plan                 = sub.plan.value        if sub.plan   else None,
        status               = sub.status.value      if sub.status else None,
        current_period_end   = sub.current_period_end,
        cancel_at_period_end = sub.cancel_at_period_end,
    )


# ── 6. Stripe webhook ─────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """
    Receives events pushed by Stripe (subscription changes, payments, etc.)
    and keeps our DB in sync.

    ⚠️  Three rules for this endpoint:
        1. Read raw bytes — never call request.json() here.
        2. No JWT auth — Stripe authenticates via the signature header instead.
        3. Always return 200 quickly; do heavy work in a Celery task if needed.
    """
    payload = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

    try:
        event = construct_webhook_event(payload, stripe_signature)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook parse error: {e}")

    result = await handle_webhook_event(event, db)
    return JSONResponse(content={"received": True, **result})