#!/usr/bin/env python3
"""
stripe_setup.py
===============
Run ONCE to create the Stripe products and prices in your sandbox.
Creates both USD (US/Canada) and INR (India) prices.
Prints all price IDs to paste into your .env file.

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
print(f"✅  Product:        {product.id}  ({product.name})\n")

# ── USD Monthly price ($9.99 / month) ─────────────────────────────────────────
price_monthly_usd = stripe.Price.create(
    product=product.id,
    unit_amount=999,       # $9.99
    currency="usd",
    recurring={"interval": "month"},
    nickname="Pro Monthly USD",
    metadata={"plan": "pro_monthly", "region": "usd"},
)
print(f"✅  Monthly USD:    {price_monthly_usd.id}  (${price_monthly_usd.unit_amount / 100:.2f}/mo)")

# ── USD Yearly price ($79.99 / year) ──────────────────────────────────────────
price_yearly_usd = stripe.Price.create(
    product=product.id,
    unit_amount=7999,      # $79.99  (~33% saving vs monthly)
    currency="usd",
    recurring={"interval": "year"},
    nickname="Pro Yearly USD",
    metadata={"plan": "pro_yearly", "region": "usd"},
)
print(f"✅  Yearly USD:     {price_yearly_usd.id}  (${price_yearly_usd.unit_amount / 100:.2f}/yr)\n")

# ── INR Monthly price (₹129 / month) ──────────────────────────────────────────
price_monthly_inr = stripe.Price.create(
    product=product.id,
    unit_amount=12900,     # ₹129.00  (Stripe uses paise — smallest INR unit)
    currency="inr",
    recurring={"interval": "month"},
    nickname="Pro Monthly INR",
    metadata={"plan": "pro_monthly", "region": "inr"},
)
print(f"✅  Monthly INR:    {price_monthly_inr.id}  (₹{price_monthly_inr.unit_amount / 100:.0f}/mo)")

# ── INR Yearly price (₹999 / year) ────────────────────────────────────────────
price_yearly_inr = stripe.Price.create(
    product=product.id,
    unit_amount=99900,     # ₹999.00  (~35% saving vs monthly)
    currency="inr",
    recurring={"interval": "year"},
    nickname="Pro Yearly INR",
    metadata={"plan": "pro_yearly", "region": "inr"},
)
print(f"✅  Yearly INR:     {price_yearly_inr.id}  (₹{price_yearly_inr.unit_amount / 100:.0f}/yr)\n")

# ── Output ─────────────────────────────────────────────────────────────────────
print("=" * 66)
print("Paste these into your .env file:")
print("=" * 66)
print(f"STRIPE_PRICE_ID_PRO_MONTHLY={price_monthly_usd.id}")
print(f"STRIPE_PRICE_ID_PRO_YEARLY={price_yearly_usd.id}")
print(f"STRIPE_PRICE_ID_PRO_MONTHLY_INR={price_monthly_inr.id}")
print(f"STRIPE_PRICE_ID_PRO_YEARLY_INR={price_yearly_inr.id}")
print("=" * 66)

print("""
Next steps:
  1. Paste the price IDs above into your .env
  2. Start the backend:  docker compose up --build
  3. Forward webhooks:   docker compose --profile stripe up stripe-cli
  4. Copy the whsec_... secret from the CLI output into .env as STRIPE_WEBHOOK_SECRET
  5. Restart backend:    docker compose restart backend

Stripe test cards:
  USD:  4242 4242 4242 4242  |  any future date  |  any CVC
  INR:  4000 0035 6000 0008  |  any future date  |  any CVC  (Indian card)
""")