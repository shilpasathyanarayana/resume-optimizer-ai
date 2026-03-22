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

from datetime import datetime
import enum

from sqlalchemy import (
    Column, Boolean, DateTime, ForeignKey,
    String, Enum as SAEnum,
)
from sqlalchemy.dialects.mysql import INTEGER  # gives us UNSIGNED support

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

    # Must match users table exactly: InnoDB + utf8mb4
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    # INTEGER(unsigned=True) matches users.id  INT UNSIGNED  exactly
    id      = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)

    # FK -> users.id (INT UNSIGNED)
    user_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Stripe IDs
    stripe_customer_id     = Column(String(64), nullable=True, index=True)
    stripe_subscription_id = Column(String(64), nullable=True, index=True)
    stripe_price_id        = Column(String(64), nullable=True)

    # Plan & status
    plan   = Column(SAEnum(PlanType),           nullable=False, default=PlanType.free)
    status = Column(SAEnum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.inactive)
    is_pro = Column(Boolean,                    nullable=False, default=False)

    # Billing period
    current_period_start = Column(DateTime, nullable=True)
    current_period_end   = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean,  nullable=False, default=False)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<Subscription user_id={self.user_id} "
            f"plan={self.plan} status={self.status} is_pro={self.is_pro}>"
        )