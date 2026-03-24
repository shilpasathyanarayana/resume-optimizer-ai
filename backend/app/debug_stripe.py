"""
debug_stripe.py
===============
Run this to diagnose why DB is not updating after payment.

Usage:
    cd backend
    source venv/bin/activate
    python debug_stripe.py
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

async def main():
    print("\n" + "="*60)
    print("STRIPE → DB DEBUG CHECKLIST")
    print("="*60)

    # ── 1. Check env vars ─────────────────────────────────────────
    print("\n[1] ENV VARS")
    secret   = os.getenv("STRIPE_SECRET_KEY", "")
    webhook  = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    monthly  = os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY", "")
    yearly   = os.getenv("STRIPE_PRICE_ID_PRO_YEARLY", "")
    frontend = os.getenv("FRONTEND_ORIGIN", "")

    print(f"  STRIPE_SECRET_KEY         : {'✅ ' + secret[:12] + '...' if secret.startswith('sk_test_') else '❌ MISSING or not test key'}")
    print(f"  STRIPE_WEBHOOK_SECRET     : {'✅ set' if webhook.startswith('whsec_') else '❌ MISSING or wrong format'}")
    print(f"  STRIPE_PRICE_ID_PRO_MONTHLY: {'✅ ' + monthly if monthly.startswith('price_') else '❌ MISSING'}")
    print(f"  STRIPE_PRICE_ID_PRO_YEARLY : {'✅ ' + yearly  if yearly.startswith('price_')  else '❌ MISSING'}")
    print(f"  FRONTEND_ORIGIN           : {'✅ ' + frontend if frontend else '⚠️  not set — success/cancel URLs may be wrong'}")

    # ── 2. Check recent Stripe checkout sessions ──────────────────
    print("\n[2] RECENT CHECKOUT SESSIONS (last 5)")
    try:
        sessions = stripe.checkout.Session.list(limit=5)
        for s in sessions.data:
            meta    = s.get("metadata", {})
            user_id = meta.get("user_id", "MISSING ❌")
            plan    = meta.get("plan",    "MISSING ❌")
            print(f"  Session : {s.id}")
            print(f"    status      : {s.status}")
            print(f"    customer    : {s.customer}")
            print(f"    subscription: {s.subscription}")
            print(f"    metadata.user_id : {user_id}")
            print(f"    metadata.plan    : {plan}")
            print()
    except Exception as e:
        print(f"  ❌ Could not fetch sessions: {e}")

    # ── 3. Check recent subscriptions ────────────────────────────
    print("\n[3] RECENT SUBSCRIPTIONS (last 5)")
    try:
        subs = stripe.Subscription.list(limit=5)
        for s in subs.data:
            meta    = s.get("metadata", {})
            user_id = meta.get("user_id", "MISSING ❌")
            plan    = meta.get("plan",    "MISSING ❌")
            print(f"  Subscription: {s.id}")
            print(f"    status           : {s.status}")
            print(f"    customer         : {s.customer}")
            print(f"    metadata.user_id : {user_id}")
            print(f"    metadata.plan    : {plan}")
            print()
    except Exception as e:
        print(f"  ❌ Could not fetch subscriptions: {e}")

    # ── 4. Check recent webhook events ───────────────────────────
    print("\n[4] RECENT WEBHOOK EVENTS (last 10)")
    try:
        events = stripe.Event.list(limit=10)
        for e in events.data:
            print(f"  {e.type:<45} {e.created}")
    except Exception as e:
        print(f"  ❌ Could not fetch events: {e}")

    # ── 5. DB check ───────────────────────────────────────────────
    print("\n[5] DB SUBSCRIPTION ROWS")
    try:
        import sys
        sys.path.insert(0, ".")
        from app.database import AsyncSessionLocal
        from app.models.subscription import Subscription
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Subscription).limit(10))
            rows   = result.scalars().all()
            if not rows:
                print("  ⚠️  No subscription rows found in DB at all")
            for r in rows:
                print(f"  user_id={r.user_id} plan={r.plan} is_pro={r.is_pro} "
                      f"status={r.status} customer={r.stripe_customer_id}")
    except Exception as e:
        print(f"  ❌ DB check failed: {e}")

    print("\n" + "="*60)
    print("DIAGNOSIS TIPS")
    print("="*60)
    print("""
  Most common causes of DB not updating:

  A) metadata.user_id is MISSING in checkout session
     → Fix: check create_checkout_session() sets metadata correctly

  B) STRIPE_WEBHOOK_SECRET is wrong
     → Webhook hits backend but returns 400 (signature mismatch)
     → Fix: copy whsec_... fresh from 'stripe listen' terminal

  C) Webhook not reaching backend at all
     → 'stripe listen' terminal is not running
     → Fix: run: stripe listen --forward-to localhost:8000/api/payments/webhook

  D) Wrong webhook URL
     → Fix: URL must match exactly what your router registers
     → Check: main.py — what prefix is payment router mounted at?

  E) DB session not committed
     → async db.commit() missing or exception swallowed silently
    """)

asyncio.run(main())
