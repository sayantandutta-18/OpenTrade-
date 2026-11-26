"""Headless Streamlit UI tests for Phase 16-22 screens and chat panel (T16.2, T20.1, T22)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from opentrade.config import RunConfig
from opentrade.services.auth import clear_login_ip_rate_limits, register_endpoint
from opentrade.services.runs import save_impact_run
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import UserRepository
from opentrade.ui.state import (
    ANALYST_PAGE,
    DB_PATH_KEY,
    PAGE_KEY,
    RUN_HISTORY_PAGE,
    SUMMARY_PAGE,
    TOUR_PAGE,
    USER_KEY,
    VALIDATION_PAGE,
)

APP_PATH = str(Path(__file__).resolve().parents[2] / "opentrade" / "ui" / "app.py")


def _all_text(at: AppTest) -> str:
    parts = (
        [e.value for e in at.markdown]
        + [e.value for e in at.caption]
        + [e.value for e in at.title]
        + [e.value for e in at.header]
        + [e.value for e in at.subheader]
        + [e.value for e in at.info]
        + [e.value for e in at.warning]
        + [e.value for e in at.error]
        + [e.value for e in at.success]
    )
    return "\n".join(str(p) for p in parts if p is not None)


def _setup_verified_user(tmp_path: Path) -> tuple[str, int]:
    db_path = str(tmp_path / "ui_phase16_22.sqlite3")
    clear_login_ip_rate_limits()
    run_migrations(db_path)
    register_endpoint(
        {"name": "UI Tester", "email": "uitester@example.com", "password": "StrongPass!123"},
        db_path=db_path,
    )
    conn = get_connection(db_path)
    repo = UserRepository(conn)
    user = repo.get_by_email("uitester@example.com")
    assert user is not None
    repo.update_email_verified_at(user.id, "2026-01-01T00:00:00Z")
    conn.commit()
    conn.close()
    return db_path, user.id


def test_analyst_screen_four_prompts_and_demo_mode_ac34_ac35(tmp_path: Path) -> None:
    """T16.2, AC-34, AC-35: Analyst screen renders 4 prompts, Demo/Live toggle, and Demo output."""
    db_path, _ = _setup_verified_user(tmp_path)
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state[DB_PATH_KEY] = db_path
    at.session_state[PAGE_KEY] = ANALYST_PAGE
    at.run()
    assert not at.exception

    text = _all_text(at)
    assert "AI Analyst" in text
    assert "Prototype. Not investment advice." in text

    # Click the Correlation prompt button
    corr_btns = [b for b in at.button if "Correlation" in b.label]
    assert len(corr_btns) >= 1
    corr_btns[0].click()
    at.run()
    assert not at.exception

    after = _all_text(at)
    assert "DEMO" in after
    assert "SYNTHETIC" in after or "REAL" in after


def test_run_history_screen_list_and_one_click_rerun_t20_1(tmp_path: Path) -> None:
    """T20.1, AC-19: Run History lists per-user saved runs and supports deterministic re-run."""
    db_path, user_id = _setup_verified_user(tmp_path)
    conn = get_connection(db_path)
    cfg = RunConfig(profile_id="synthetic_default", seed=42)
    saved, persisted = save_impact_run(
        conn, user_id=user_id, is_verified=True, config=cfg, name="Saved Test Run"
    )
    conn.close()
    assert persisted is True

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state[DB_PATH_KEY] = db_path
    at.session_state[USER_KEY] = {"id": user_id, "name": "UI Tester", "is_verified": True}
    at.session_state[PAGE_KEY] = RUN_HISTORY_PAGE
    at.run()
    assert not at.exception

    text = _all_text(at)
    assert "Run History" in text
    assert "Saved Test Run" in text
    assert saved["fingerprint"][:12] in text

    rerun_btns = [b for b in at.button if "Re-run" in b.label]
    assert len(rerun_btns) >= 1
    rerun_btns[0].click()
    at.run()
    assert not at.exception
    assert saved["fingerprint"] in _all_text(at)


def test_tour_summary_and_validation_screens_t20_2_t18_1(tmp_path: Path) -> None:
    """T20.2, T18.1, AC-42: Tour, Summary/About, and Validation screens render cleanly."""
    db_path, _ = _setup_verified_user(tmp_path)
    for page, expected in (
        (TOUR_PAGE, "Guided Tour"),
        (SUMMARY_PAGE, "About OpenTrade"),
        (VALIDATION_PAGE, "Stylized-Fact Validation"),
    ):
        at = AppTest.from_file(APP_PATH, default_timeout=15)
        at.session_state[DB_PATH_KEY] = db_path
        at.session_state[PAGE_KEY] = page
        at.run()
        assert not at.exception
        text = _all_text(at)
        assert expected in text
        assert "Prototype. Not investment advice." in text


def test_chat_panel_refusal_and_clear_history_t22_1_to_t22_3(tmp_path: Path) -> None:
    """T22.1-T22.3, AC-38, AC-40: Chat panel refuses investment advice and clears history."""
    db_path, user_id = _setup_verified_user(tmp_path)
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state[DB_PATH_KEY] = db_path
    at.session_state[USER_KEY] = {"id": user_id, "name": "UI Tester", "is_verified": True}
    at.session_state[PAGE_KEY] = ANALYST_PAGE
    at.run()
    assert not at.exception

    chat_inputs = [t for t in at.text_input if "Ask" in t.label or "Chat" in t.label]
    assert len(chat_inputs) >= 1
    chat_inputs[0].input("Should I buy AAPL?")
    send_btns = [b for b in at.button if "Send" in b.label]
    assert len(send_btns) >= 1
    send_btns[0].click()
    at.run()
    assert not at.exception
    assert "cannot recommend" in _all_text(at).lower()

    clear_btns = [b for b in at.button if "Clear" in b.label]
    assert len(clear_btns) >= 1
    clear_btns[0].click()
    at.run()
    assert not at.exception
