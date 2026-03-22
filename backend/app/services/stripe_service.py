"""
services/stripe_service.py
===========================
All Stripe interactions live here — routers stay thin and just call these.

Flow:
  router  →  stripe_service  →  Stripe API
                             →  DB (via SQLAlchemy async session)

Webhook events update the DB so is_pro is always in sync with Stripe.
"""

import stripe
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.subscription import Subscription, PlanType, SubscriptionStatus

# ── Initialise Stripe with your secret key ────────────────────────────────────
stripe.api_key = settings.STRIPE_SECRET_KEY


# ── Plan catalogue ────────────────────────────────────────────────────────────
# price_id values come from .env — set them once with stripe_setup.py
PLANS: dict[str, dict] = {
    "pro_monthly": {
        "name":     "Resume Optimizer Pro (Monthly)",
        "price_id": settings.STRIPE_PRICE_ID_PRO_MONTHLY,
        "amount":   999,       # $9.99 in cents
        "interval": "month",
        "features": [
            "Unlimited resume optimisations",
            "ATS keyword gap analysis",
            "AI cover letter generator",
            "Priority processing",
            "Download PDF & DOCX",
        ],
    },
    "pro_yearly": {
        "name":     "Resume Optimizer Pro (Yearly)",
        "price_id": settings.STRIPE_PRICE_ID_PRO_YEARLY,
        "amount":   7999,      # $79.99 in cents  (~33% off)
        "interval": "year",
        "features": [
            "Everything in Monthly",
            "2 months free",
            "Early access to new features",
            "LinkedIn optimisation (coming soon)",
        ],
    },
}


# ── Checkout session ──────────────────────────────────────────────────────────

async def create_checkout_session(
    plan_key: str,
    user_id:  int,
    user_email: str,
) -> stripe.checkout.Session:
    """
    Creates a Stripe Checkout session for the chosen plan.
    Stores user_id in metadata so the webhook can find the right DB row.
    """
    plan = PLANS.get(plan_key)
    if not plan:
        raise ValueError(f"Unknown plan '{plan_key}'. Choose: {list(PLANS)}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": plan["price_id"], "quantity": 1}],
        metadata={
            "user_id": str(user_id),
            "plan":    plan_key,
        },
        subscription_data={
            "metadata": {"user_id": str(user_id), "plan": plan_key},
        },
        # {CHECKOUT_SESSION_ID} is a Stripe literal — NOT a Python f-string variable.
        # Stripe replaces it server-side before redirecting the user.
        success_url=(
            f"{settings.FRONTEND_ORIGIN}/payment-success.html"
            "?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{settings.FRONTEND_ORIGIN}/pricing.html?cancelled=true",
        billing_address_collection="auto",
        allow_promotion_codes=True,
    )
    return session


# ── Customer portal ───────────────────────────────────────────────────────────

async def create_portal_session(
    customer_id: str,
) -> stripe.billing_portal.Session:
    """
    Opens the Stripe-hosted portal: user can update card, cancel, etc.
    Requires the customer_id stored in our subscriptions table.
    """
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.FRONTEND_ORIGIN}/dashboard.html",
    )


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_or_create_subscription(
    db: AsyncSession,
    user_id: int,
) -> Subscription:
    """Returns the Subscription row for a user, creating it (free) if absent."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id)
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
    return sub


async def get_subscription_by_stripe_id(
    db: AsyncSession,
    stripe_subscription_id: str,
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription_id
        )
    )
    return result.scalar_one_or_none()


async def get_subscription_by_customer_id(
    db: AsyncSession,
    stripe_customer_id: str,
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_customer_id == stripe_customer_id
        )
    )
    return result.scalar_one_or_none()


# ── Webhook event processing ──────────────────────────────────────────────────

def construct_webhook_event(
    payload: bytes,
    sig_header: str,
) -> stripe.Event:
    """
    Validates the Stripe-Signature header.
    Raises stripe.error.SignatureVerificationError on tampered payloads.
    """
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )


async def handle_webhook_event(
    event: stripe.Event,
    db: AsyncSession,
) -> dict:
    """
    Routes each Stripe event type to the right DB update.
    Returns a summary dict for logging.

    To add your own side-effects (emails, Celery tasks, etc.) look for
    the  # TODO  comments in each branch.
    """
    etype = event["type"]
    data  = event["data"]["object"]
    result = {"event": etype, "handled": True, "action": None}

    # ── Checkout completed ────────────────────────────────────────────────────
    if etype == "checkout.session.completed":
        user_id     = int(data["metadata"].get("user_id", 0))
        customer_id = data.get("customer")
        if user_id:
            sub = await get_or_create_subscription(db, user_id)
            sub.stripe_customer_id = customer_id
            await db.commit()
            result["action"] = f"stored customer_id={customer_id} for user={user_id}"

    # ── Subscription created ──────────────────────────────────────────────────
    elif etype == "customer.subscription.created":
        await _sync_subscription(db, data)
        result["action"] = "subscription activated"
        # TODO: send welcome / upgrade email via email_service

    # ── Subscription updated (renewal, plan change, cancel-at-period-end) ─────
    elif etype == "customer.subscription.updated":
        await _sync_subscription(db, data)
        result["action"] = f"subscription synced status={data.get('status')}"

    # ── Subscription deleted / fully cancelled ────────────────────────────────
    elif etype == "customer.subscription.deleted":
        sub = await get_subscription_by_stripe_id(db, data["id"])
        if sub:
            sub.is_pro  = False
            sub.status  = SubscriptionStatus.cancelled
            sub.plan    = PlanType.free
            await db.commit()
        result["action"] = "subscription cancelled → is_pro=False"
        # TODO: send cancellation email

    # ── Payment succeeded (monthly renewal) ──────────────────────────────────
    elif etype == "invoice.payment_succeeded":
        # Re-sync so current_period_end stays fresh after each renewal
        sub_id = data.get("subscription")
        if sub_id:
            stripe_sub = stripe.Subscription.retrieve(sub_id)
            await _sync_subscription(db, stripe_sub)
        result["action"] = "renewal confirmed, period updated"
        # TODO: add to payment history table, send receipt email

    # ── Payment failed ────────────────────────────────────────────────────────
    elif etype == "invoice.payment_failed":
        customer_id = data.get("customer")
        sub = await get_subscription_by_customer_id(db, customer_id)
        if sub:
            sub.status = SubscriptionStatus.past_due
            await db.commit()
        result["action"] = "marked past_due"
        # TODO: send dunning email via email_service

    else:
        result["handled"] = False

    return result


# ── Internal sync helper ──────────────────────────────────────────────────────

async def _sync_subscription(
    db: AsyncSession,
    stripe_sub: dict,          # stripe.Subscription object (dict-like)
) -> None:
    """
    Takes a Stripe Subscription object and writes its state to our DB row.
    Called by both 'created' and 'updated' event handlers.
    """
    stripe_sub_id  = stripe_sub["id"]
    customer_id    = stripe_sub["customer"]
    stripe_status  = stripe_sub["status"]
    meta           = stripe_sub.get("metadata", {})
    user_id        = int(meta.get("user_id", 0))
    plan_key       = meta.get("plan", "pro_monthly")

    # Map Stripe status → our enum
    status_map = {
        "active":   SubscriptionStatus.active,
        "trialing": SubscriptionStatus.trialing,
        "past_due": SubscriptionStatus.past_due,
        "canceled": SubscriptionStatus.cancelled,
        "cancelled":SubscriptionStatus.cancelled,
        "incomplete":SubscriptionStatus.inactive,
    }
    db_status = status_map.get(stripe_status, SubscriptionStatus.inactive)
    is_pro    = db_status in (SubscriptionStatus.active, SubscriptionStatus.trialing)

    # Get price_id from the first line item
    price_id = None
    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")

    # Billing period
    period_start = datetime.utcfromtimestamp(stripe_sub["current_period_start"]) \
        if stripe_sub.get("current_period_start") else None
    period_end   = datetime.utcfromtimestamp(stripe_sub["current_period_end"]) \
        if stripe_sub.get("current_period_end") else None

    # Try to find by subscription ID first, then by customer ID
    sub = await get_subscription_by_stripe_id(db, stripe_sub_id)
    if sub is None and customer_id:
        sub = await get_subscription_by_customer_id(db, customer_id)
    if sub is None and user_id:
        sub = await get_or_create_subscription(db, user_id)

    if sub is None:
        return  # can't match — log this in production

    sub.stripe_subscription_id = stripe_sub_id
    sub.stripe_customer_id     = customer_id
    sub.stripe_price_id        = price_id
    sub.plan                   = PlanType(plan_key) if plan_key in PlanType.__members__ \
                                 else PlanType.pro_monthly
    sub.status                 = db_status
    sub.is_pro                 = is_pro
    sub.current_period_start   = period_start
    sub.current_period_end     = period_end
    sub.cancel_at_period_end   = stripe_sub.get("cancel_at_period_end", False)
    sub.updated_at             = datetime.utcnow()

    await db.commit()