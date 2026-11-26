"""Headless Streamlit UI tests for Market Data (T7.3) and News Panel (T8.2).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-28 to AC-31, AC-41, AC-42) and docs/USER_FLOW.md (Flow 7).
"""

from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

from opentrade.services.auth import clear_login_ip_rate_limits, register_endpoint
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import UserRepository

APP_PATH = str(Path(__file__).resolve().parents[2] / "opentrade" / "ui" / "app.py")


def _all_text(at: AppTest) -> str:
    """Collect visible text across standard Streamlit elements."""
    chunks: list[str] = []
    for attr in (
        "markdown",
        "caption",
        "info",
        "warning",
        "error",
        "success",
        "title",
        "header",
        "subheader",
        "text",
    ):
        for el in getattr(at, attr, []):
            val = getattr(el, "value", "")
            if val:
                chunks.append(str(val))
    for metric in getattr(at, "metric", []):
        chunks.append(f"{metric.label}: {metric.value}")
    return "\n".join(chunks)


def _find_button(at: AppTest, label: str) -> Any:
    """Find a button by exact label in the rendered AppTest tree."""
    for btn in at.button:
        if btn.label == label:
            return btn
    raise AssertionError(f"Button {label!r} not found; available: {[b.label for b in at.button]}")


def test_market_data_panel_displays_quote_history_and_watchlist_t7_3(tmp_path: Path) -> None:
    """T7.3, AC-28, AC-29, AC-42: Market Data shows quote, chart, SIMULATED badge, and watchlist."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "ui_market.db"
    run_migrations(db_path)
    register_endpoint(
        {"name": "Trader", "email": "mkt@example.com", "password": "MarketPassword99!"},
        db_path=db_path,
    )
    conn = get_connection(db_path)
    try:
        user = UserRepository(conn).get_by_email("mkt@example.com")
        assert user is not None
        user_id = user.id
    finally:
        conn.close()

    # Demo mode watchlist stays in session state
    at_demo = AppTest.from_file(APP_PATH, default_timeout=15)
    at_demo.session_state["current_page"] = "market_data"
    at_demo.run()
    assert not at_demo.exception
    rendered = _all_text(at_demo)
    assert "Prototype. Not investment advice." in rendered
    assert "SIMULATED" in rendered
    _find_button(at_demo, "Add to watchlist").click().run()
    assert not at_demo.exception
    assert "AAPL" in at_demo.session_state["demo_watchlist"]

    # Verified user persists watchlist to SQLite
    at_auth = AppTest.from_file(APP_PATH, default_timeout=15)
    at_auth.session_state["db_path"] = str(db_path)
    at_auth.session_state["current_page"] = "market_data"
    at_auth.session_state["user"] = {"id": user_id, "email": "mkt@example.com", "verified": True}
    at_auth.run()
    _find_button(at_auth, "Add to watchlist").click().run()
    assert not at_auth.exception
    assert "SIMULATED" in _all_text(at_auth)


def test_news_panel_demo_and_live_fallback_t8_2() -> None:
    """T8.2, AC-30, AC-31, AC-42: News panel shows DEMO headlines and falls back cleanly on Live."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["current_page"] = "news_lab"
    at.run()
    assert not at.exception

    rendered = _all_text(at)
    assert "Prototype. Not investment advice." in rendered
    assert "DEMO" in rendered
    assert "ago" in rendered

    # Switch to Live mode (no feeds configured / offline -> graceful fallback to DEMO)
    at.radio[0].set_value("Live").run()
    assert not at.exception
    after_live = _all_text(at)
    assert "Live news is unavailable right now" in after_live
    assert "DEMO" in after_live
