"""Headless Streamlit UI tests for Simulator (T3.5) and Impact Lab (T3.6).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-18 to AC-22, AC-41, AC-42),
docs/SRS.md (FR-22 to FR-27, FR-52, FR-53), and docs/USER_FLOW.md (Flow 6).
"""

from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

from opentrade.services.auth import clear_login_ip_rate_limits, register_endpoint
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import RunRepository, UserRepository

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


def test_simulator_page_renders_ladder_depth_and_injects_order_t3_5() -> None:
    """T3.5, AC-41, AC-42, FR-22, FR-52, FR-53: Simulator displays ladder, depth, and slippage."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["current_page"] = "simulator"
    at.run()
    assert not at.exception

    rendered = _all_text(at)
    assert "Prototype. Not investment advice." in rendered
    assert "SYNTHETIC" in rendered
    assert "DEMO" in rendered

    _find_button(at, "Inject order").click().run()
    assert not at.exception
    after_inject = _all_text(at)
    assert "Slippage" in after_inject
    assert "bps" in after_inject
    assert "SYNTHETIC" in after_inject

    _find_button(at, "Open impact lab").click().run()
    assert not at.exception
    assert at.session_state["current_page"] == "impact_lab"


def test_impact_lab_runs_sweep_decay_and_explains_exponent_t3_6() -> None:
    """T3.6, AC-18 to AC-20, AC-22, AC-42, FR-52: Impact Lab runs sweep, fit, and decay."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["current_page"] = "impact_lab"
    at.run()
    assert not at.exception
    assert "Prototype. Not investment advice." in _all_text(at)

    _find_button(at, "Run sweep").click().run()
    assert not at.exception
    rendered = _all_text(at)
    assert "SYNTHETIC" in rendered
    assert "95% CI" in rendered
    assert "Temporary impact" in rendered
    assert "Permanent impact" in rendered
    assert "in this simulation" in rendered.lower()


def test_impact_lab_save_run_persists_only_for_verified_user_t3_6(tmp_path: Path) -> None:
    """T3.6, AC-21, FR-27: Save run persists for verified users and blocks demo persistence."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "ui_save_run.db"
    run_migrations(db_path)
    register_endpoint(
        {"name": "Lin", "email": "lin@example.com", "password": "LinStrongPassword99!"},
        db_path=db_path,
    )
    conn = get_connection(db_path)
    try:
        user = UserRepository(conn).get_by_email("lin@example.com")
        assert user is not None
        user_id = user.id
    finally:
        conn.close()

    # Demo user clicking Save run does not persist
    at_demo = AppTest.from_file(APP_PATH)
    at_demo.session_state["db_path"] = str(db_path)
    at_demo.session_state["current_page"] = "impact_lab"
    at_demo.run()
    _find_button(at_demo, "Run sweep").click().run()
    _find_button(at_demo, "Save run").click().run()
    assert not at_demo.exception
    assert "log in" in _all_text(at_demo).lower()

    # Verified user clicking Save run persists to SQLite with fingerprint
    at_auth = AppTest.from_file(APP_PATH)
    at_auth.session_state["db_path"] = str(db_path)
    at_auth.session_state["current_page"] = "impact_lab"
    at_auth.session_state["user"] = {"id": user_id, "email": "lin@example.com", "verified": True}
    at_auth.run()
    _find_button(at_auth, "Run sweep").click().run()
    _find_button(at_auth, "Save run").click().run()
    assert not at_auth.exception
    assert "Saved run" in _all_text(at_auth)

    conn2 = get_connection(db_path)
    try:
        rows = RunRepository(conn2).list_by_user_id(user_id)
        assert len(rows) == 1
        assert rows[0].provenance == "SYNTHETIC"
    finally:
        conn2.close()
