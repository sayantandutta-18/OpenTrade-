"""Headless Streamlit UI tests for prototype banner and home page (T0.16).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-42), docs/SRS.md (FR-52, FR-53),
and docs/USER_FLOW.md (Flow 1).
"""

from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "opentrade" / "ui" / "app.py")


def _all_rendered_text(at: AppTest) -> str:
    """Collect visible text across standard Streamlit elements."""
    chunks: list[str] = []
    for attr in ("markdown", "caption", "info", "warning", "title", "header", "subheader", "text"):
        elements = getattr(at, attr, [])
        for el in elements:
            val = getattr(el, "value", "")
            if val:
                chunks.append(str(val))
    return "\n".join(chunks)


def _find_button(at: AppTest, label: str) -> Any:
    """Find a button by exact label in the rendered AppTest tree."""
    for btn in at.button:
        if btn.label == label:
            return btn
    raise AssertionError(f"Button {label!r} not found; available: {[b.label for b in at.button]}")


def test_prototype_banner_renders_on_home_and_all_routes() -> None:
    """AC-42, FR-53: Prototype banner text renders on the Home page and every routed page state."""
    for page in ("home", "login", "register", "simulator"):
        at = AppTest.from_file(APP_PATH, default_timeout=15)
        at.session_state["current_page"] = page
        at.run()
        assert not at.exception
        rendered = _all_rendered_text(at)
        assert "Prototype. Not investment advice." in rendered


def test_home_page_shows_synthetic_and_demo_provenance_labels() -> None:
    """FR-52, AC-42: Home page renders explicit SYNTHETIC and DEMO provenance text labels."""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    rendered = _all_rendered_text(at)
    assert "SYNTHETIC" in rendered
    assert "DEMO" in rendered


def test_home_demo_button_initializes_demo_mode_seed_42_and_routes_to_simulator() -> None:
    """FR-52, FR-53: Clicking Demo sets demo mode with seed 42 and routes to simulator."""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception

    demo_btn = _find_button(at, "Start in demo mode")
    demo_btn.click().run()

    assert not at.exception
    assert at.session_state["current_page"] == "simulator"
    assert at.session_state["mode"] == "DEMO"
    assert at.session_state["demo_seed"] == 42

    rendered = _all_rendered_text(at)
    assert "Demo mode. Runs are not saved. Create an account to keep them." in rendered
    assert "Prototype. Not investment advice." in rendered


def test_home_login_and_register_buttons_navigate_cleanly() -> None:
    """US-1, FR-53: Clicking Log in and Register navigates to login and register page states."""
    at_login = AppTest.from_file(APP_PATH)
    at_login.run()
    _find_button(at_login, "Log in").click().run()
    assert not at_login.exception
    assert at_login.session_state["current_page"] == "login"
    assert "Prototype. Not investment advice." in _all_rendered_text(at_login)

    at_register = AppTest.from_file(APP_PATH)
    at_register.run()
    _find_button(at_register, "Register").click().run()
    assert not at_register.exception
    assert at_register.session_state["current_page"] == "register"
    assert "Prototype. Not investment advice." in _all_rendered_text(at_register)
