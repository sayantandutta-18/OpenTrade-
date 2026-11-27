"""Headless Streamlit UI tests for Terms & Conditions and Subscription pages."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from opentrade.services.auth import clear_login_ip_rate_limits, register_endpoint
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import UserRepository
from opentrade.ui.state import (
    DB_PATH_KEY,
    PAGE_KEY,
    REGISTER_PAGE,
    SUBSCRIPTION_PAGE,
    TERMS_PAGE,
    USER_KEY,
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


def test_register_blocks_signup_when_terms_unchecked(tmp_path: Path) -> None:
    """Register form blocks signup with a validation error if Terms checkbox is unchecked."""
    db_path = str(tmp_path / "reg_terms.db")
    run_migrations(db_path)

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state[DB_PATH_KEY] = db_path
    at.session_state[PAGE_KEY] = REGISTER_PAGE
    at.run()
    assert not at.exception

    for inp in at.text_input:
        if inp.label == "Name":
            inp.input("Rohan")
        elif inp.label == "Email":
            inp.input("rohan@example.com")
        elif inp.label in ("Password", "Confirm password"):
            inp.input("StrongPassphrase99!")

    # Do NOT check terms checkbox -> click Create account
    btn = [b for b in at.button if b.label == "Create account"][0]
    btn.click().run()
    assert not at.exception
    assert "terms & conditions" in _all_text(at).lower()


def test_terms_and_subscription_pages_render_and_activate_inr_plan(tmp_path: Path) -> None:
    """Terms & Conditions and Subscription pages render and allow activating an INR Pro plan."""
    clear_login_ip_rate_limits()
    db_path = str(tmp_path / "sub_ui.db")
    run_migrations(db_path)
    register_endpoint(
        {
            "name": "Sub User",
            "email": "subuser@example.com",
            "password": "VeryStrongPassword99!",
            "terms_accepted": True,
        },
        db_path=db_path,
    )
    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("subuser@example.com")
    conn.close()
    assert user is not None

    # Terms page
    at_terms = AppTest.from_file(APP_PATH, default_timeout=15)
    at_terms.session_state[DB_PATH_KEY] = db_path
    at_terms.session_state[PAGE_KEY] = TERMS_PAGE
    at_terms.run()
    assert not at_terms.exception
    assert "Terms & Conditions" in _all_text(at_terms)
    assert "Not Financial or Investment Advice" in _all_text(at_terms)

    # Subscription page
    at_sub = AppTest.from_file(APP_PATH, default_timeout=15)
    at_sub.session_state[DB_PATH_KEY] = db_path
    at_sub.session_state[USER_KEY] = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "is_verified": True,
    }
    at_sub.session_state[PAGE_KEY] = SUBSCRIPTION_PAGE
    at_sub.run()
    assert not at_sub.exception
    txt = _all_text(at_sub)
    assert "999" in txt and "3,999" in txt and "7,999" in txt

    act_btns = [b for b in at_sub.button if "Activate Pro Annual" in b.label]
    assert len(act_btns) == 1
    act_btns[0].click().run()
    assert not at_sub.exception
    assert "Pro Annual" in _all_text(at_sub)
