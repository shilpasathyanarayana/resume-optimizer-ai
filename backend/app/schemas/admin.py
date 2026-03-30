"""
schemas/admin.py
Pydantic response models for the admin endpoints.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdminUserRow(BaseModel):
    """One row in the admin user list — users JOIN subscriptions."""
    # ── users table ──────────────────────────────────────────────
    id:           int
    name:         str
    email:        str
    is_active:    bool
    is_verified:  bool
    monthly_usage: int
    created_at:   datetime

    # ── subscriptions table (nullable — user may have no row) ────
    is_pro:               bool
    subscription_plan:    Optional[str]   = None   # free | pro_monthly | pro_yearly
    subscription_status:  Optional[str]   = None   # active | trialing | past_due | cancelled | inactive
    current_period_end:   Optional[datetime] = None
    cancel_at_period_end: bool = False

    model_config = {"from_attributes": True}


class AdminUsersResponse(BaseModel):
    total:  int
    users:  list[AdminUserRow]