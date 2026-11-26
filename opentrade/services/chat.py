"""Full chatbot service: streaming, citations, guardrails, confirmed actions, limits (T22)."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from opentrade.llm.guardrails import ADVICE_REFUSAL_TEXT, is_advice_request
from opentrade.services.errors import NotFoundError, RateLimitedError, ValidationError
from opentrade.storage.chat_repo import ChatRepository
from opentrade.storage.db import get_connection

MAX_MESSAGE_CHARS = 4000
ACTION_EXPIRY_MINUTES = 10
ALLOWED_CHAT_ACTIONS = ("save_run", "delete_run", "add_company")


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def stream_chat_turn(
    conn: sqlite3.Connection,
    user_id: int,
    message: str,
    screen_context: dict[str, Any] | None = None,
    daily_limit: int = 50,
    now: datetime | None = None,
) -> Iterator[str]:
    """Stream a grounded assistant reply enforcing daily limits and guardrails (AC-37/38/40)."""
    clean_msg = (message or "").strip()
    if not clean_msg or len(clean_msg) > MAX_MESSAGE_CHARS:
        raise ValidationError(f"Message must be 1 to {MAX_MESSAGE_CHARS} characters")

    ref_now = now or datetime.now(UTC)
    day_start = _iso(ref_now.replace(hour=0, minute=0, second=0, microsecond=0))
    repo = ChatRepository(conn)
    if repo.count_user_turns_since(user_id=user_id, since_iso=day_start) >= daily_limit:
        raise RateLimitedError("Daily chat limit reached", code="DAILY_LIMIT")

    now_str = _iso(ref_now)
    repo.add_message(user_id=user_id, role="user", content=clean_msg, created_at=now_str)

    if is_advice_request(clean_msg):
        reply = ADVICE_REFUSAL_TEXT
    else:
        ctx = screen_context or {}
        run_id = str(ctx.get("run_id") or ctx.get("fingerprint") or "demo")
        prov = str(ctx.get("provenance") or "SYNTHETIC")
        nums = [
            f"{k}={v}"
            for k, v in ctx.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        summary = ", ".join(nums) if nums else "simulation context ready"
        reply = f"In this simulation, {summary} (run {run_id}, {prov})."

    repo.add_message(user_id=user_id, role="assistant", content=reply, created_at=now_str)
    for token in reply.split(" "):
        yield token + " "


def propose_chat_action(
    conn: sqlite3.Connection,
    user_id: int,
    action: str,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a pending action awaiting explicit confirmation within 10 minutes (AC-39)."""
    if action not in ALLOWED_CHAT_ACTIONS:
        raise ValidationError(f"Unsupported chat action: {action!r}")

    ref_now = now or datetime.now(UTC)
    expires_at = _iso(ref_now + timedelta(minutes=ACTION_EXPIRY_MINUTES))
    action_id = str(uuid.uuid4())
    row = ChatRepository(conn).create_pending_action(
        action_id=action_id,
        user_id=user_id,
        action=action,
        payload_json=json.dumps(payload),
        expires_at=expires_at,
        created_at=_iso(ref_now),
    )
    return {
        "id": row.id,
        "action": row.action,
        "payload": payload,
        "status": "PENDING_CONFIRMATION",
        "expires_at": row.expires_at,
    }


def confirm_chat_action(
    conn: sqlite3.Connection,
    user_id: int,
    action_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Confirm and execute a pending chat action if owned and unexpired (AC-39)."""
    repo = ChatRepository(conn)
    row = repo.get_pending_action(action_id=action_id, user_id=user_id)
    if row is None:
        raise NotFoundError("Pending action not found")
    if row.status != "PENDING":
        raise ValidationError(f"Action already processed with status {row.status}")

    ref_now = now or datetime.now(UTC)
    exp_dt = datetime.fromisoformat(row.expires_at.replace("Z", "+00:00"))
    if ref_now > exp_dt:
        repo.update_action_status(action_id, user_id, "EXPIRED")
        raise ValidationError("This request expired. Ask again.")

    repo.update_action_status(action_id, user_id, "CONFIRMED")
    repo.add_message(
        user_id=user_id,
        role="system_action",
        content=f"Confirmed action {row.action}",
        created_at=_iso(ref_now),
    )
    return {
        "id": row.id,
        "action": row.action,
        "payload": json.loads(row.payload_json),
        "status": "CONFIRMED",
    }


def get_chat_history(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    """Return active chat messages for user_id."""
    rows = ChatRepository(conn).list_active_messages(user_id=user_id)
    return [
        {"id": r.id, "role": r.role, "content": r.content, "created_at": r.created_at} for r in rows
    ]


def clear_chat_history(
    conn: sqlite3.Connection,
    user_id: int,
    now: datetime | None = None,
) -> int:
    """Soft-delete all chat history for user_id (AC-40)."""
    return ChatRepository(conn).soft_delete_messages(
        user_id=user_id,
        deleted_at=_iso(now or datetime.now(UTC)),
    )


def chat_turn_db_path(
    db_path: str | Path | None,
    user_id: int | None,
    message: str,
    screen_context: dict[str, Any] | None = None,
) -> str:
    """UI-safe helper running a chat turn (persisted for logged-in user, read-only for demo)."""
    if user_id is None:
        from opentrade.services.assistant import answer_screen_question

        return str(answer_screen_question(message, screen_context)["reply"])
    conn = get_connection(db_path)
    try:
        return "".join(stream_chat_turn(conn, user_id, message, screen_context))
    finally:
        conn.close()


def get_chat_history_db_path(
    db_path: str | Path | None, user_id: int | None
) -> list[dict[str, Any]]:
    """UI-safe helper returning active chat messages for user_id."""
    if user_id is None:
        return []
    conn = get_connection(db_path)
    try:
        return get_chat_history(conn, user_id)
    finally:
        conn.close()


def propose_action_db_path(
    db_path: str | Path | None,
    user_id: int,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """UI-safe helper proposing a pending chat action."""
    conn = get_connection(db_path)
    try:
        return propose_chat_action(conn, user_id, action, payload)
    finally:
        conn.close()


def confirm_action_db_path(
    db_path: str | Path | None,
    user_id: int,
    action_id: str,
) -> dict[str, Any]:
    """UI-safe helper confirming a pending chat action."""
    conn = get_connection(db_path)
    try:
        return confirm_chat_action(conn, user_id, action_id)
    finally:
        conn.close()


def clear_chat_db_path(db_path: str | Path | None, user_id: int | None) -> int:
    """UI-safe helper soft-deleting chat history for user_id."""
    if user_id is None:
        return 0
    conn = get_connection(db_path)
    try:
        return clear_chat_history(conn, user_id)
    finally:
        conn.close()
