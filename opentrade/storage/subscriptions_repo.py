"""Repository for user subscriptions and billing history (PostgreSQL & SQLite)."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SubscriptionRow:
    """Immutable representation of a row in the subscriptions table."""

    id: int
    user_id: int
    plan_code: str
    plan_name: str
    amount_inr: int
    billing_cycle: str
    status: str
    started_at: str
    expires_at: str
    payment_ref: str | None
    created_at: str


def _row_to_sub(row: tuple[Any, ...]) -> SubscriptionRow:
    return SubscriptionRow(
        id=int(row[0]),
        user_id=int(row[1]),
        plan_code=str(row[2]),
        plan_name=str(row[3]),
        amount_inr=int(row[4]),
        billing_cycle=str(row[5]),
        status=str(row[6]),
        started_at=str(row[7]),
        expires_at=str(row[8]),
        payment_ref=str(row[9]) if row[9] is not None else None,
        created_at=str(row[10]),
    )


class SubscriptionsRepository:
    """Repository handling parameterized SQL for subscriptions."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def create_subscription(
        self,
        user_id: int,
        plan_code: str,
        plan_name: str,
        amount_inr: int,
        billing_cycle: str,
        status: str,
        started_at: str,
        expires_at: str,
        payment_ref: str | None,
        created_at: str,
    ) -> SubscriptionRow:
        """Insert a new subscription row and return it."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO subscriptions (
                    user_id, plan_code, plan_name, amount_inr, billing_cycle,
                    status, started_at, expires_at, payment_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    user_id,
                    plan_code,
                    plan_name,
                    amount_inr,
                    billing_cycle,
                    status,
                    started_at,
                    expires_at,
                    payment_ref,
                    created_at,
                ),
            )
            sub_id = cursor.lastrowid
            if sub_id is None:
                raise RuntimeError("Failed to retrieve lastrowid after subscription insert")
            return SubscriptionRow(
                id=int(sub_id),
                user_id=user_id,
                plan_code=plan_code,
                plan_name=plan_name,
                amount_inr=amount_inr,
                billing_cycle=billing_cycle,
                status=status,
                started_at=started_at,
                expires_at=expires_at,
                payment_ref=payment_ref,
                created_at=created_at,
            )
        finally:
            cursor.close()

    def get_active_subscription(self, user_id: int, now_iso: str) -> SubscriptionRow | None:
        """Return the latest active non-expired subscription for user_id."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, plan_code, plan_name, amount_inr, billing_cycle,
                       status, started_at, expires_at, payment_ref, created_at
                FROM subscriptions
                WHERE user_id = ? AND status = 'active' AND expires_at > ?
                ORDER BY id DESC
                LIMIT 1;
                """,
                (user_id, now_iso),
            )
            row = cursor.fetchone()
            return _row_to_sub(row) if row else None
        finally:
            cursor.close()

    def list_user_subscriptions(self, user_id: int) -> list[SubscriptionRow]:
        """Return subscription billing history for user_id, newest first."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, plan_code, plan_name, amount_inr, billing_cycle,
                       status, started_at, expires_at, payment_ref, created_at
                FROM subscriptions
                WHERE user_id = ?
                ORDER BY id DESC;
                """,
                (user_id,),
            )
            return [_row_to_sub(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def cancel_active_subscriptions(self, user_id: int) -> int:
        """Mark all currently active subscriptions for user_id as cancelled."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE subscriptions
                SET status = 'cancelled'
                WHERE user_id = ? AND status = 'active';
                """,
                (user_id,),
            )
            return int(getattr(cursor, "rowcount", 0) or 0)
        finally:
            cursor.close()

    def expire_elapsed_subscriptions(self, user_id: int, now_iso: str) -> int:
        """Mark active subscriptions whose expires_at <= now_iso as expired."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE subscriptions
                SET status = 'expired'
                WHERE user_id = ? AND status = 'active' AND expires_at <= ?;
                """,
                (user_id, now_iso),
            )
            return int(getattr(cursor, "rowcount", 0) or 0)
        finally:
            cursor.close()
