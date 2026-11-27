"""INR subscription plans, activation/upgrade, and billing history service."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from opentrade.services.errors import ValidationError
from opentrade.storage.db import get_connection
from opentrade.storage.subscriptions_repo import SubscriptionRow, SubscriptionsRepository


@dataclass(frozen=True)
class SubscriptionPlan:
    """Immutable definition of an OpenTrade INR subscription tier."""

    code: str
    name: str
    amount_inr: int
    duration_days: int
    billing_cycle: str
    badge: str
    savings_note: str
    features: tuple[str, ...]


SUBSCRIPTION_PLANS: dict[str, SubscriptionPlan] = {
    "monthly_999": SubscriptionPlan(
        code="monthly_999",
        name="Pro Monthly",
        amount_inr=999,
        duration_days=30,
        billing_cycle="monthly",
        badge="",
        savings_note="Flexible monthly access",
        features=(
            "Live Market Data (Twelve Data)",
            "AI Analyst & Research Chat",
            "Unlimited Saved Runs & Cross-Impact",
        ),
    ),
    "half_yearly_3999": SubscriptionPlan(
        code="half_yearly_3999",
        name="Pro 6-Month",
        amount_inr=3999,
        duration_days=180,
        billing_cycle="6_months",
        badge="Popular",
        savings_note="Saves ₹1,995 vs monthly",
        features=(
            "Live Market Data (Twelve Data)",
            "AI Analyst & Research Chat",
            "Unlimited Saved Runs & Cross-Impact",
        ),
    ),
    "yearly_7999": SubscriptionPlan(
        code="yearly_7999",
        name="Pro Annual",
        amount_inr=7999,
        duration_days=365,
        billing_cycle="yearly",
        badge="Best Value",
        savings_note="Saves ₹3,989 vs monthly",
        features=(
            "Live Market Data (Twelve Data)",
            "AI Analyst & Research Chat",
            "Unlimited Saved Runs & Cross-Impact",
        ),
    ),
}


def list_plans() -> list[SubscriptionPlan]:
    """Return ordered list of paid INR subscription plans."""
    return [
        SUBSCRIPTION_PLANS["monthly_999"],
        SUBSCRIPTION_PLANS["half_yearly_3999"],
        SUBSCRIPTION_PLANS["yearly_7999"],
    ]


def _format_sub(row: SubscriptionRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "plan_code": row.plan_code,
        "plan_name": row.plan_name,
        "amount_inr": row.amount_inr,
        "billing_cycle": row.billing_cycle,
        "status": row.status,
        "started_at": row.started_at,
        "expires_at": row.expires_at,
        "payment_ref": row.payment_ref,
        "created_at": row.created_at,
    }


def activate_subscription(
    conn: Any,
    user_id: int,
    plan_code: str,
    payment_ref: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Activate or upgrade a user's INR subscription plan."""
    plan = SUBSCRIPTION_PLANS.get(plan_code)
    if plan is None:
        raise ValidationError(f"Unknown subscription plan: {plan_code!r}")

    ref_now = (now or datetime.now(UTC)).astimezone(UTC)
    started_at = ref_now.isoformat()
    expires_at = (ref_now + timedelta(days=plan.duration_days)).isoformat()
    clean_ref = (payment_ref or "").strip() or f"demo_pay_{uuid.uuid4().hex[:12]}"

    repo = SubscriptionsRepository(conn)
    repo.cancel_active_subscriptions(user_id=user_id)
    row = repo.create_subscription(
        user_id=user_id,
        plan_code=plan.code,
        plan_name=plan.name,
        amount_inr=plan.amount_inr,
        billing_cycle=plan.billing_cycle,
        status="active",
        started_at=started_at,
        expires_at=expires_at,
        payment_ref=clean_ref,
        created_at=started_at,
    )
    return _format_sub(row)


def get_user_subscription_status(
    conn: Any,
    user_id: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return active subscription summary, days remaining, and billing history."""
    ref_now = (now or datetime.now(UTC)).astimezone(UTC)
    now_iso = ref_now.isoformat()
    repo = SubscriptionsRepository(conn)
    repo.expire_elapsed_subscriptions(user_id=user_id, now_iso=now_iso)
    active = repo.get_active_subscription(user_id=user_id, now_iso=now_iso)
    history = [_format_sub(r) for r in repo.list_user_subscriptions(user_id=user_id)]

    days_remaining = 0
    if active is not None:
        exp_dt = datetime.fromisoformat(active.expires_at)
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=UTC)
        days_remaining = max(0, (exp_dt - ref_now).days)

    return {
        "is_pro": active is not None,
        "tier": active.plan_name if active is not None else "Free / Demo",
        "active": _format_sub(active) if active is not None else None,
        "days_remaining": days_remaining,
        "history": history,
    }


def cancel_user_subscription(conn: Any, user_id: int) -> int:
    """Cancel any active subscription for user_id."""
    return SubscriptionsRepository(conn).cancel_active_subscriptions(user_id=user_id)


def activate_subscription_db_path(
    db_path: str | Path | None,
    user_id: int,
    plan_code: str,
    payment_ref: str | None = None,
) -> dict[str, Any]:
    """UI-safe helper activating a subscription plan."""
    conn = get_connection(db_path)
    try:
        return activate_subscription(
            conn, user_id=user_id, plan_code=plan_code, payment_ref=payment_ref
        )
    finally:
        conn.close()


def get_subscription_status_db_path(
    db_path: str | Path | None,
    user_id: int | None,
) -> dict[str, Any]:
    """UI-safe helper returning subscription status and billing history."""
    if user_id is None:
        return {
            "is_pro": False,
            "tier": "Free / Demo",
            "active": None,
            "days_remaining": 0,
            "history": [],
        }
    conn = get_connection(db_path)
    try:
        return get_user_subscription_status(conn, user_id=user_id)
    finally:
        conn.close()


def cancel_subscription_db_path(db_path: str | Path | None, user_id: int) -> int:
    """UI-safe helper cancelling an active subscription."""
    conn = get_connection(db_path)
    try:
        return cancel_user_subscription(conn, user_id=user_id)
    finally:
        conn.close()
