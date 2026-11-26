"""Tests for Basic Assistant (T17.1) and Full Chatbot (T22.1-T22.3).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-37 to AC-40) and docs/SECURITY.md (T-8, T-11).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from opentrade.services.assistant import answer_screen_question
from opentrade.services.auth import clear_login_ip_rate_limits, register_endpoint
from opentrade.services.chat import (
    clear_chat_history,
    confirm_chat_action,
    get_chat_history,
    propose_chat_action,
    stream_chat_turn,
)
from opentrade.services.errors import NotFoundError, RateLimitedError, ValidationError
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import UserRepository

ADVICE_PHRASINGS = [
    "what should i buy",
    "Which stock should I buy right now?",
    "Tell me what to sell",
    "Should I buy AAPL?",
    "Should I sell TSLA today?",
    "Recommend a stock for me",
    "Give me investment advice",
    "What is the best stock to invest in?",
    "Which ticker will go up tomorrow?",
    "Pick a winning stock for my portfolio",
    "How should I allocate my money?",
    "Advise me on buying NVDA",
    "Can you tell me if JPM will rise?",
    "What trade should I place next?",
    "Is XOM a buy or a sell?",
    "Give me a hot stock tip",
    "Which company is guaranteed to profit?",
    "Should I go long or short on MSFT?",
    "What should I invest $1000 in?",
    "Tell me which stocks to purchase",
]


def test_advice_refusal_across_20_phrasings_ac38_t17_1() -> None:
    """T17.1, T22.1, AC-38: Assistant refuses investment advice across 20 fixed phrasings."""
    ctx = {"screen": "impact_lab", "run_id": "run123", "provenance": "SYNTHETIC", "beta": 0.51}
    for phrase in ADVICE_PHRASINGS:
        ans = answer_screen_question(phrase, screen_context=ctx)
        assert ans["refused"] is True
        assert "cannot recommend" in ans["reply"].lower()

    ok = answer_screen_question("What does beta 0.51 mean here?", screen_context=ctx)
    assert ok["refused"] is False
    assert "0.51" in ok["reply"]


def test_chat_streaming_citations_actions_and_limits_ac37_ac39_ac40(tmp_path: Path) -> None:
    """T22.1-T22.3, AC-37, AC-39, AC-40: Citations, confirmed actions with expiry, limits, clear."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "chat.db"
    run_migrations(db_path)
    register_endpoint(
        {"name": "ChatUser", "email": "chat@example.com", "password": "ChatStrongPassword1!"},
        db_path=db_path,
    )
    register_endpoint(
        {"name": "OtherUser", "email": "other@example.com", "password": "OtherStrongPassword1!"},
        db_path=db_path,
    )

    conn = get_connection(db_path)
    try:
        user = UserRepository(conn).get_by_email("chat@example.com")
        other = UserRepository(conn).get_by_email("other@example.com")
        assert user is not None and other is not None

        # AC-37: Streamed reply with number includes citation
        ctx = {"run_id": "3f9a1234", "provenance": "SYNTHETIC", "beta": 0.52}
        chunks = list(
            stream_chat_turn(
                conn=conn,
                user_id=user.id,
                message="Summarize my run exponent",
                screen_context=ctx,
                daily_limit=3,
            )
        )
        full_reply = "".join(chunks)
        assert "0.52" in full_reply
        assert "3f9a1234" in full_reply and "SYNTHETIC" in full_reply

        # AC-40: Daily limit returns 429 DAILY_LIMIT
        list(stream_chat_turn(conn, user.id, "Second turn", ctx, daily_limit=3))
        list(stream_chat_turn(conn, user.id, "Third turn", ctx, daily_limit=3))
        with pytest.raises(RateLimitedError) as exc_lim:
            list(stream_chat_turn(conn, user.id, "Fourth turn", ctx, daily_limit=3))
        assert exc_lim.value.code == "DAILY_LIMIT"
        assert exc_lim.value.status_code == 429

        # AC-39: Pending action requires confirmation and respects 10-min expiry + user isolation
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        action = propose_chat_action(
            conn=conn,
            user_id=user.id,
            action="add_company",
            payload={"symbol": "AAPL"},
            now=now,
        )
        assert action["status"] == "PENDING_CONFIRMATION"

        # Cross-user confirm returns 404 NOT_FOUND
        with pytest.raises(NotFoundError):
            confirm_chat_action(conn, other.id, action["id"], now=now + timedelta(minutes=1))

        # Confirm within 10 min succeeds
        confirmed = confirm_chat_action(conn, user.id, action["id"], now=now + timedelta(minutes=2))
        assert confirmed["status"] == "CONFIRMED"

        # Expired action (>10 min) rejected
        expired_act = propose_chat_action(
            conn=conn, user_id=user.id, action="save_run", payload={"name": "Exp"}, now=now
        )
        with pytest.raises(ValidationError, match="expired"):
            confirm_chat_action(conn, user.id, expired_act["id"], now=now + timedelta(minutes=11))

        # AC-40: Clear history soft-deletes user's chat messages
        assert len(get_chat_history(conn, user.id)) >= 2
        clear_chat_history(conn, user.id)
        assert get_chat_history(conn, user.id) == []
    finally:
        conn.close()
