#!/usr/bin/env python3
"""
stripe_setup.py
===============
Run ONCE to create the Stripe products and prices in your sandbox.
Prints the price IDs to paste into your .env file.

Usage:
    cd backend
    python stripe_setup.py
"""

import os
import stripe
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

if not stripe.api_key:
    print("❌  STRIPE_SECRET_KEY not set in .env")
    exit(1)

if not stripe.api_key.startswith("sk_test_"):
    print("⚠️   Warning: this doesn't look like a test key (sk_test_...)")
    print("    Continuing anyway — make sure you want to run this in production!")

print("🔧  Creating Stripe products and prices...\n")

# ── Product ────────────────────────────────────────────────────────────────────
product = stripe.Product.create(
    name="Resume Optimizer Pro",
    description=(
        "Unlimited AI-powered resume optimisation, "
        "ATS keyword analysis, and cover letter generator."
    ),
    metadata={"app": "resume-optimizer-ai"},
)
print(f"✅  Product:        {product.id}  ({product.name})")

# ── Monthly price ──────────────────────────────────────────────────────────────
price_monthly = stripe.Price.create(
    product=product.id,
    unit_amount=999,       # $9.99
    currency="usd",
    recurring={"interval": "month"},
    nickname="Pro Monthly",
    metadata={"plan": "pro_monthly"},
)
print(f"✅  Monthly price:  {price_monthly.id}  (${price_monthly.unit_amount/100:.2f}/mo)")

# ── Yearly price ───────────────────────────────────────────────────────────────
price_yearly = stripe.Price.create(
    product=product.id,
    unit_amount=7999,      # $79.99  (~33% saving vs monthly)
    currency="usd",
    recurring={"interval": "year"},
    nickname="Pro Yearly",
    metadata={"plan": "pro_yearly"},
)
print(f"✅  Yearly price:   {price_yearly.id}  (${price_yearly.unit_amount/100:.2f}/yr)\n")

# ── Output ─────────────────────────────────────────────────────────────────────
print("=" * 62)
print("Paste these into your .env file:")
print("=" * 62)
print(f"STRIPE_PRICE_ID_PRO_MONTHLY={price_monthly.id}")
print(f"STRIPE_PRICE_ID_PRO_YEARLY={price_yearly.id}")
print("=" * 62)

print("""
Next steps:
  1. Paste the price IDs above into your .env
  2. Start the backend:  docker compose up --build
  3. Forward webhooks:   docker compose --profile stripe up stripe-cli
  4. Copy the whsec_... secret from the CLI output into .env as STRIPE_WEBHOOK_SECRET
  5. Restart backend:    docker compose restart backend

Stripe test card:  4242 4242 4242 4242  |  any future date  |  any CVC
""")
