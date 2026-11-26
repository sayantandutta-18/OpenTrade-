"""Tests for quote, history, and per-user watchlist services (T7.2).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-6, AC-7, AC-28, AC-29)
and docs/SRS.md (FR-33 to FR-36, FR-52).
"""

from pathlib import Path

from opentrade.adapters.market_twelvedata import AdapterError, HistoryBar, QuoteData
from opentrade.services.auth import (
    clear_login_ip_rate_limits,
    delete_user_account,
    register_endpoint,
)
from opentrade.services.market import (
    add_to_watchlist,
    get_history,
    get_quote,
    list_watchlist,
    remove_from_watchlist,
)
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import UserRepository


class _SuccessAdapter:
    def fetch_quote(self, symbol: str) -> QuoteData:
        return QuoteData(
            symbol=symbol,
            price=200.0,
            change=2.0,
            change_pct=1.01,
            open=198.0,
            prev_close=198.0,
            high=201.0,
            low=197.5,
            source="twelvedata",
            as_of="2026-01-15T16:00:00Z",
        )

    def fetch_history(self, symbol: str, days: int = 60) -> list[HistoryBar]:
        return [
            HistoryBar(
                date=f"2026-01-{10 + i:02d}",
                open=190.0 + i,
                high=192.0 + i,
                low=189.0 + i,
                close=191.0 + i,
                volume=1_000_000,
            )
            for i in range(5)
        ]


class _FailingAdapter:
    def fetch_quote(self, symbol: str) -> QuoteData:
        raise AdapterError("Upstream unavailable")

    def fetch_history(self, symbol: str, days: int = 60) -> list[HistoryBar]:
        raise AdapterError("Upstream unavailable")


def test_quote_fallback_shows_simulated_never_real_ac28() -> None:
    """T7.2, AC-28, FR-52: Failing or unconfigured quote returns SIMULATED badge, never REAL."""
    live = get_quote("AAPL", adapter=_SuccessAdapter())
    assert live["label"] == "REAL"
    assert live["price"] == 200.0
    assert live["source"] == "twelvedata"

    fallback = get_quote("AAPL", adapter=_FailingAdapter())
    assert fallback["label"] == "SIMULATED"
    assert fallback["reason"]
    assert fallback["price"] > 0

    no_adapter = get_quote("AAPL", adapter=None)
    assert no_adapter["label"] == "SIMULATED"


def test_history_returns_points_with_real_or_simulated_label() -> None:
    """T7.2, FR-34, FR-52: History returns OHLCV points tagged REAL or SIMULATED."""
    live_hist = get_history("AAPL", days=60, adapter=_SuccessAdapter())
    assert live_hist["label"] == "REAL"
    assert len(live_hist["points"]) == 5

    sim_hist = get_history("AAPL", days=60, adapter=_FailingAdapter())
    assert sim_hist["label"] == "SIMULATED"
    assert len(sim_hist["points"]) == 60


def test_watchlist_crud_badges_isolation_and_cascade_ac29_ac6(tmp_path: Path) -> None:
    """T7.2, AC-6, AC-7, AC-29: Watchlist rows carry REAL or SIMULATED badge and isolate users."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "watchlist.db"
    run_migrations(db_path)

    register_endpoint(
        {"name": "UserA", "email": "wa@example.com", "password": "WatchlistPasswordA1!"},
        db_path=db_path,
    )
    register_endpoint(
        {"name": "UserB", "email": "wb@example.com", "password": "WatchlistPasswordB1!"},
        db_path=db_path,
    )

    conn = get_connection(db_path)
    try:
        user_a = UserRepository(conn).get_by_email("wa@example.com")
        user_b = UserRepository(conn).get_by_email("wb@example.com")
        assert user_a is not None and user_b is not None

        add_to_watchlist(conn, user_a.id, "AAPL")
        add_to_watchlist(conn, user_a.id, "MSFT")
        add_to_watchlist(conn, user_b.id, "JPM")

        items_a = list_watchlist(conn, user_a.id, adapter=_SuccessAdapter())
        assert [i["symbol"] for i in items_a] == ["AAPL", "MSFT"]
        assert all(i["label"] in ("REAL", "SIMULATED") for i in items_a)

        items_b_sim = list_watchlist(conn, user_b.id, adapter=_FailingAdapter())
        assert [i["symbol"] for i in items_b_sim] == ["JPM"]
        assert items_b_sim[0]["label"] == "SIMULATED"

        # User A removing JPM does not affect User B's watchlist
        assert remove_from_watchlist(conn, user_a.id, "JPM") is False
        assert len(list_watchlist(conn, user_b.id, adapter=_FailingAdapter())) == 1

        # Deleting User A cascades watchlist_items
        delete_user_account(conn, user_a, "WatchlistPasswordA1!")
        assert list_watchlist(conn, user_a.id, adapter=_FailingAdapter()) == []
        assert len(list_watchlist(conn, user_b.id, adapter=_FailingAdapter())) == 1
    finally:
        conn.close()
