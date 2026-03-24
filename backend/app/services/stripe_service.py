"""
services/stripe_service.py
===========================
All Stripe interactions live here — routers stay thin and just call these.

Flow:
  router  →  stripe_service  →  Stripe API
                             →  DB (via SQLAlchemy async session)

Webhook events update the DB so is_pro is always in sync with Stripe.

Fix applied:
  checkout.session.completed now does a full subscription sync instead of
  only storing customer_id. This is necessary because
  customer.subscription.created fires with empty metadata (Stripe does NOT
  copy checkout session metadata to the subscription object automatically),
  so _sync_subscription() could not resolve the user_id from that event.
"""

import stripe
from datetime import datetime
from sqlalchemy import select, update
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


# ── Shared status map ─────────────────────────────────────────────────────────
_STATUS_MAP: dict[str, SubscriptionStatus] = {
    "active":    SubscriptionStatus.active,
    "trialing":  SubscriptionStatus.trialing,
    "past_due":  SubscriptionStatus.past_due,
    "canceled":  SubscriptionStatus.cancelled,   # Stripe uses one-L spelling
    "cancelled": SubscriptionStatus.cancelled,
    "incomplete": SubscriptionStatus.inactive,
}


# ── Checkout session ──────────────────────────────────────────────────────────

async def create_checkout_session(
    plan_key:   str,
    user_id:    int,
    user_email: str,
) -> stripe.checkout.Session:
    """
    Creates a Stripe Checkout session for the chosen plan.
    Stores user_id + plan in BOTH session metadata AND subscription_data
    metadata so every downstream webhook event carries the user reference.
    """
    plan = PLANS.get(plan_key)
    if not plan:
        raise ValueError(f"Unknown plan '{plan_key}'. Choose: {list(PLANS)}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": plan["price_id"], "quantity": 1}],
        # Stored on the Session object — readable in checkout.session.completed
        metadata={
            "user_id": str(user_id),
            "plan":    plan_key,
        },
        # Stored on the Subscription object — readable in subscription.* events
        subscription_data={
            "metadata": {"user_id": str(user_id), "plan": plan_key},
        },
        # {CHECKOUT_SESSION_ID} is a Stripe literal — NOT a Python f-string var.
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
    payload:    bytes,
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
    db:    AsyncSession,
) -> dict:
    """
    Routes each Stripe event type to the right DB update.
    Returns a summary dict for logging.

    Event handling strategy
    -----------------------
    checkout.session.completed
        → PRIMARY upgrade path.  Retrieves the full Subscription object from
          Stripe and writes all fields (is_pro, plan, period dates, etc.) in
          one go.  Also syncs the users.plan column so JWTs stay accurate.

    customer.subscription.created / updated
        → SECONDARY sync.  By the time these fire, checkout.session.completed
          has already stored the customer_id, so _sync_subscription() can
          resolve the DB row via customer_id even when metadata is empty.

    customer.subscription.deleted
        → Marks user as free / cancelled.

    invoice.payment_succeeded
        → Refreshes current_period_end after each renewal.

    invoice.payment_failed
        → Marks subscription as past_due.
    """
    etype  = event["type"]
    data   = event["data"]["object"]
    result = {"event": etype, "handled": True, "action": None}

    # ── Checkout completed ────────────────────────────────────────────────────
    # This is the PRIMARY place we upgrade a user.
    # We retrieve the Stripe Subscription here so we have full period dates.
    if etype == "checkout.session.completed":
        user_id         = int(data["metadata"].get("user_id", 0))
        customer_id     = data.get("customer")
        subscription_id = data.get("subscription")   # ← key fix: use this

        if not user_id:
            result["action"] = "skipped — no user_id in metadata"
            return result

        if not subscription_id:
            # Free plan checkout (no subscription object) — just store customer
            sub = await get_or_create_subscription(db, user_id)
            sub.stripe_customer_id = customer_id
            await db.commit()
            result["action"] = f"stored customer_id for user={user_id} (no subscription)"
            return result

        # Retrieve the full subscription so we have current_period_end etc.
        stripe_sub = stripe.Subscription.retrieve(subscription_id)

        plan_key  = data["metadata"].get("plan", "pro_monthly")
        db_status = _STATUS_MAP.get(stripe_sub["status"], SubscriptionStatus.active)
        is_pro    = db_status in (SubscriptionStatus.active, SubscriptionStatus.trialing)

        period_start = _ts(stripe_sub.get("current_period_start"))
        period_end   = _ts(stripe_sub.get("current_period_end"))

        # Get price_id from subscription line items
        items    = stripe_sub.get("items", {}).get("data", [])
        price_id = items[0].get("price", {}).get("id") if items else None

        sub = await get_or_create_subscription(db, user_id)
        sub.stripe_customer_id     = customer_id
        sub.stripe_subscription_id = stripe_sub["id"]
        sub.stripe_price_id        = price_id
        sub.plan                   = _plan(plan_key)
        sub.status                 = db_status
        sub.is_pro                 = is_pro
        sub.current_period_start   = period_start
        sub.current_period_end     = period_end
        sub.cancel_at_period_end   = stripe_sub.get("cancel_at_period_end", False)
        sub.updated_at             = datetime.utcnow()
        await db.commit()

        # ── Also update users.plan so the JWT reflects the new plan ──────────
        await _sync_user_plan(db, user_id, "pro" if is_pro else "free")

        result["action"] = (
            f"user={user_id} upgraded → plan={plan_key} "
            f"is_pro={is_pro} status={db_status}"
        )

    # ── Subscription created ──────────────────────────────────────────────────
    # checkout.session.completed already did the heavy lifting.
    # This call keeps things in sync just in case (e.g. API-created subs).
    elif etype == "customer.subscription.created":
        await _sync_subscription(db, data)
        result["action"] = "subscription created — synced"
        # TODO: send welcome / upgrade email via email_service

    # ── Subscription updated (renewal, plan change, cancel-at-period-end) ─────
    elif etype == "customer.subscription.updated":
        await _sync_subscription(db, data)
        result["action"] = f"subscription updated — status={data.get('status')}"

    # ── Subscription deleted / fully cancelled ────────────────────────────────
    elif etype == "customer.subscription.deleted":
        sub = await get_subscription_by_stripe_id(db, data["id"])
        if sub:
            sub.is_pro  = False
            sub.status  = SubscriptionStatus.cancelled
            sub.plan    = PlanType.free
            sub.updated_at = datetime.utcnow()
            await db.commit()
            await _sync_user_plan(db, sub.user_id, "free")
        result["action"] = "subscription cancelled → is_pro=False"
        # TODO: send cancellation email

    # ── Payment succeeded (monthly renewal) ──────────────────────────────────
    elif etype == "invoice.payment_succeeded":
        # Re-sync so current_period_end stays fresh after each renewal
        sub_id = data.get("subscription")
        if sub_id:
            stripe_sub = stripe.Subscription.retrieve(sub_id)
            await _sync_subscription(db, stripe_sub)
        result["action"] = "renewal confirmed — period updated"
        # TODO: add to payment history table, send receipt email

    # ── Payment failed ────────────────────────────────────────────────────────
    elif etype == "invoice.payment_failed":
        customer_id = data.get("customer")
        sub = await get_subscription_by_customer_id(db, customer_id)
        if sub:
            sub.status     = SubscriptionStatus.past_due
            sub.updated_at = datetime.utcnow()
            await db.commit()
        result["action"] = "marked past_due"
        # TODO: send dunning email via email_service

    else:
        result["handled"] = False

    return result


# ── Internal sync helper ──────────────────────────────────────────────────────

async def _sync_subscription(
    db:         AsyncSession,
    stripe_sub: dict,          # stripe.Subscription object (dict-like)
) -> None:
    """
    Takes a Stripe Subscription object and writes its state to our DB row.
    Called by subscription.created / updated / invoice.payment_succeeded.

    Lookup order (most → least reliable):
      1. stripe_subscription_id  — exact match
      2. stripe_customer_id      — set by checkout.session.completed
      3. metadata.user_id        — fallback for API-created subscriptions

    Note: We deliberately do NOT call get_or_create_subscription() here as
    a last resort because if we can't identify the user we'd create an
    orphaned row with user_id=0 which breaks the FK constraint.
    """
    stripe_sub_id = stripe_sub["id"]
    customer_id   = stripe_sub["customer"]
    stripe_status = stripe_sub["status"]
    meta          = stripe_sub.get("metadata", {})
    user_id       = int(meta.get("user_id", 0))
    plan_key      = meta.get("plan", "pro_monthly")

    db_status = _STATUS_MAP.get(stripe_status, SubscriptionStatus.inactive)
    is_pro    = db_status in (SubscriptionStatus.active, SubscriptionStatus.trialing)

    items    = stripe_sub.get("items", {}).get("data", [])
    price_id = items[0].get("price", {}).get("id") if items else None

    period_start = _ts(stripe_sub.get("current_period_start"))
    period_end   = _ts(stripe_sub.get("current_period_end"))

    # Resolve the DB row — try three fallbacks
    sub = await get_subscription_by_stripe_id(db, stripe_sub_id)
    if sub is None and customer_id:
        sub = await get_subscription_by_customer_id(db, customer_id)
    if sub is None and user_id:
        # Only use this for API-created subscriptions (metadata will be set)
        sub = await get_or_create_subscription(db, user_id)

    if sub is None:
        # Can't identify user — log and bail (don't create orphaned rows)
        print(
            f"[stripe] _sync_subscription: cannot resolve user for "
            f"sub={stripe_sub_id} customer={customer_id} — skipping"
        )
        return

    sub.stripe_subscription_id = stripe_sub_id
    sub.stripe_customer_id     = customer_id
    sub.stripe_price_id        = price_id
    sub.plan                   = _plan(plan_key)
    sub.status                 = db_status
    sub.is_pro                 = is_pro
    sub.current_period_start   = period_start
    sub.current_period_end     = period_end
    sub.cancel_at_period_end   = stripe_sub.get("cancel_at_period_end", False)
    sub.updated_at             = datetime.utcnow()
    await db.commit()

    # Keep users.plan in sync
    if sub.user_id:
        await _sync_user_plan(db, sub.user_id, "pro" if is_pro else "free")


# ── Sync users.plan column ────────────────────────────────────────────────────

async def _sync_user_plan(
    db:      AsyncSession,
    user_id: int,
    plan:    str,           # "pro" | "free"
) -> None:
    """
    Keeps the users.plan column in sync so JWT tokens reflect the correct plan.
    Import is inline to avoid circular imports between models.
    """
    try:
        from app.models.user import User  # noqa: PLC0415
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(plan=plan)
        )
        await db.commit()
    except Exception as exc:  # pragma: no cover
        # Non-fatal — subscription table is source of truth
        print(f"[stripe] _sync_user_plan failed for user={user_id}: {exc}")


# ── Timestamp helper ──────────────────────────────────────────────────────────

def _ts(unix: int | None) -> datetime | None:
    """Converts a Unix timestamp to a UTC datetime, or None if absent."""
    return datetime.utcfromtimestamp(unix) if unix else None


# ── Plan key helper ───────────────────────────────────────────────────────────

def _plan(plan_key: str) -> PlanType:
    """Maps a plan key string to a PlanType enum, defaulting to pro_monthly."""
    return PlanType(plan_key) if plan_key in PlanType.__members__ \
        else PlanType.pro_monthly