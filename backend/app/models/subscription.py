"""
models/subscription.py
======================
Tracks each user's Stripe subscription state in MariaDB.

Relationship:  User (1) ──── (0..1) Subscription

Fix applied:
  users.id is INT UNSIGNED — so user_id here must also be
  INTEGER UNSIGNED, otherwise MariaDB raises:
  errno 150 "Foreign key constraint is incorrectly formed"
"""

"""
models/subscription.py
"""
from datetime import datetime
import enum

from sqlalchemy import (
    Column, Integer, Boolean, DateTime, ForeignKey,
    String, Enum as SAEnum,
)
from app.database import Base


class PlanType(str, enum.Enum):
    free        = "free"
    pro_monthly = "pro_monthly"
    pro_yearly  = "pro_yearly"


class SubscriptionStatus(str, enum.Enum):
    active    = "active"
    trialing  = "trialing"
    past_due  = "past_due"
    cancelled = "cancelled"
    inactive  = "inactive"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    stripe_customer_id     = Column(String(64), nullable=True, index=True)
    stripe_subscription_id = Column(String(64), nullable=True, index=True)
    stripe_price_id        = Column(String(64), nullable=True)

    plan   = Column(SAEnum(PlanType,           name="plan_type_enum"),           nullable=False, default=PlanType.free)
    status = Column(SAEnum(SubscriptionStatus, name="subscription_status_enum"), nullable=False, default=SubscriptionStatus.inactive)
    is_pro = Column(Boolean, nullable=False, default=False)

    current_period_start = Column(DateTime, nullable=True)
    current_period_end   = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean,  nullable=False, default=False)

    monthly_usage  = Column(Integer,  nullable=False, default=0)
    usage_reset_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<Subscription user_id={self.user_id} "
            f"plan={self.plan} status={self.status} is_pro={self.is_pro}>"
        )