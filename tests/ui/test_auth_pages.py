"""Headless Streamlit UI tests for register, login, verify, forgot, and reset pages (T0.17).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-10, AC-42), docs/SRS.md (FR-1 to FR-7, FR-53),
docs/USER_STORIES.md (US-1 to US-5), and docs/USER_FLOW.md (Flows 2 to 4).
"""

import re
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from opentrade.services.auth import clear_login_ip_rate_limits
from opentrade.storage.migrate import run_migrations

APP_PATH = str(Path(__file__).resolve().parents[2] / "opentrade" / "ui" / "app.py")


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    """Ensure IP login rate limits do not leak across UI tests."""
    clear_login_ip_rate_limits()


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
    return "\n".join(chunks)


def _find_button(at: AppTest, label: str) -> Any:
    """Find a button by exact label in the rendered AppTest tree."""
    for btn in at.button:
        if btn.label == label:
            return btn
    raise AssertionError(f"Button {label!r} not found; available: {[b.label for b in at.button]}")


def _find_input(at: AppTest, label: str) -> Any:
    """Find a text_input widget by exact label in the rendered AppTest tree."""
    for inp in at.text_input:
        if inp.label == label:
            return inp
    raise AssertionError(
        f"text_input {label!r} not found; available: {[i.label for i in at.text_input]}"
    )


def _extract_token(body: str) -> str:
    """Extract raw token from mock email body."""
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert match is not None, f"No token found in email body: {body!r}"
    return match.group(1)


def _new_app(db_path: Path, page: str) -> AppTest:
    """Create and run an AppTest instance pointed at a temp migrated DB and route."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["db_path"] = str(db_path)
    at.session_state["current_page"] = page
    at.run()
    assert not at.exception
    return at


def test_auth_pages_render_prototype_banner_across_all_views(tmp_path: Path) -> None:
    """AC-42, FR-53: Prototype banner text renders on all 5 auth views."""
    db_path = tmp_path / "test_banner.db"
    run_migrations(db_path)
    for page in ("register", "login", "verify", "forgot", "reset"):
        at = _new_app(db_path, page)
        assert "Prototype. Not investment advice." in _all_text(at)


def test_register_page_shows_privacy_note_and_password_rules_before_submit(
    tmp_path: Path,
) -> None:
    """AC-10, FR-1, FR-2, US-1: Register page displays privacy note and password rules upfront."""
    db_path = tmp_path / "test_reg_copy.db"
    run_migrations(db_path)
    at = _new_app(db_path, "register")
    rendered = _all_text(at)
    assert "We store your name, email, and password (hashed). Nothing else." in rendered
    assert "12 characters" in rendered
    assert "common password" in rendered.lower()


def test_register_page_success_and_duplicate_anti_enumeration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-1, FR-2A, US-1: Register displays uniform inbox message for new and duplicate emails."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)
    sent: list[dict[str, str]] = []
    monkeypatch.setattr(
        "opentrade.services.auth.send_email",
        lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}),
    )

    at = _new_app(db_path, "register")
    _find_input(at, "Name").input("Alice Trader")
    _find_input(at, "Email").input("alice@example.com")
    _find_input(at, "Password").input("CorrectHorseBatteryStaple99!")
    _find_input(at, "Confirm password").input("CorrectHorseBatteryStaple99!")
    _find_button(at, "Create account").click().run()
    assert not at.exception
    assert "Check your inbox. We sent a link to alice@example.com." in _all_text(at)
    assert _find_button(at, "Resend link") is not None
    assert len(sent) == 1

    # Duplicate registration produces identical confirmation message
    at_dup = _new_app(db_path, "register")
    _find_input(at_dup, "Name").input("Alice Clone")
    _find_input(at_dup, "Email").input("alice@example.com")
    _find_input(at_dup, "Password").input("AnotherStrongPassword88!")
    _find_input(at_dup, "Confirm password").input("AnotherStrongPassword88!")
    _find_button(at_dup, "Create account").click().run()
    assert not at_dup.exception
    assert "Check your inbox. We sent a link to alice@example.com." in _all_text(at_dup)


def test_register_page_validation_errors_mismatch_and_weak_password(tmp_path: Path) -> None:
    """FR-2, US-1: Mismatched password confirmation and weak passwords render clean errors."""
    db_path = tmp_path / "test_reg_err.db"
    run_migrations(db_path)

    at = _new_app(db_path, "register")
    _find_input(at, "Name").input("Bob")
    _find_input(at, "Email").input("bob@example.com")
    _find_input(at, "Password").input("CorrectHorseBatteryStaple99!")
    _find_input(at, "Confirm password").input("DifferentPassword99!")
    _find_button(at, "Create account").click().run()
    assert not at.exception
    assert "do not match" in _all_text(at).lower()

    at_weak = _new_app(db_path, "register")
    _find_input(at_weak, "Name").input("Bob")
    _find_input(at_weak, "Email").input("bob@example.com")
    _find_input(at_weak, "Password").input("short")
    _find_input(at_weak, "Confirm password").input("short")
    _find_button(at_weak, "Create account").click().run()
    assert not at_weak.exception
    assert len(at_weak.error) > 0


def test_verify_page_valid_token_expired_token_and_resend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-3, US-2: Verify confirms valid token, handles invalid token, and supports resend."""
    db_path = tmp_path / "test_verify.db"
    run_migrations(db_path)
    sent: list[dict[str, str]] = []
    monkeypatch.setattr(
        "opentrade.services.auth.send_email",
        lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}),
    )

    at_reg = _new_app(db_path, "register")
    _find_input(at_reg, "Name").input("Carol")
    _find_input(at_reg, "Email").input("carol@example.com")
    _find_input(at_reg, "Password").input("StrongUniquePassphrase77!")
    _find_input(at_reg, "Confirm password").input("StrongUniquePassphrase77!")
    _find_button(at_reg, "Create account").click().run()
    raw_token = _extract_token(sent[-1]["body"])

    # Invalid token shows error and offers Send a new link
    at_bad = _new_app(db_path, "verify")
    _find_input(at_bad, "Verification token").input("invalid-token-value")
    _find_button(at_bad, "Verify email").click().run()
    assert not at_bad.exception
    assert len(at_bad.error) > 0
    assert _find_button(at_bad, "Send a new link") is not None

    # Resend link works up to 3 times per hour, 4th triggers rate limit
    for _ in range(3):
        _find_input(at_bad, "Email for new link").input("carol@example.com")
        _find_button(at_bad, "Send a new link").click().run()
        assert len(at_bad.success) > 0 or len(at_bad.info) > 0
    _find_input(at_bad, "Email for new link").input("carol@example.com")
    _find_button(at_bad, "Send a new link").click().run()
    assert len(at_bad.error) > 0

    # Latest resent token verifies cleanly
    latest_token = _extract_token(sent[-1]["body"])
    assert latest_token != raw_token
    at_ok = _new_app(db_path, "verify")
    _find_input(at_ok, "Verification token").input(latest_token)
    _find_button(at_ok, "Verify email").click().run()
    assert not at_ok.exception
    assert "Your email is confirmed." in _all_text(at_ok)
    assert _find_button(at_ok, "Continue") is not None


def test_login_page_success_invalid_lockout_and_unverified_banner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-4, FR-5, US-3, US-4: Login handles success, unverified banner, errors, and lockout."""
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)
    monkeypatch.setattr("opentrade.services.auth.send_email", lambda to, subject, body: None)

    at_reg = _new_app(db_path, "register")
    _find_input(at_reg, "Name").input("Dave")
    _find_input(at_reg, "Email").input("dave@example.com")
    _find_input(at_reg, "Password").input("DaveSuperStrongPassword1!")
    _find_input(at_reg, "Confirm password").input("DaveSuperStrongPassword1!")
    _find_button(at_reg, "Create account").click().run()

    # Valid login for unverified user stores session & shows verify banner
    at_login = _new_app(db_path, "login")
    _find_input(at_login, "Email").input("dave@example.com")
    _find_input(at_login, "Password").input("DaveSuperStrongPassword1!")
    _find_button(at_login, "Log in").click().run()
    assert not at_login.exception
    assert at_login.session_state["user"]["email"] == "dave@example.com"
    assert at_login.session_state["current_page"] == "simulator"
    assert "Verify your email to save runs" in _all_text(at_login)

    # Wrong password shows uniform message; 5 failures trigger lockout message
    at_fail = _new_app(db_path, "login")
    for _ in range(4):
        _find_input(at_fail, "Email").input("dave@example.com")
        _find_input(at_fail, "Password").input("WrongPassword123!")
        _find_button(at_fail, "Log in").click().run()
        assert "Email or password is incorrect." in _all_text(at_fail)

    _find_input(at_fail, "Email").input("dave@example.com")
    _find_input(at_fail, "Password").input("WrongPassword123!")
    _find_button(at_fail, "Log in").click().run()
    # 6th attempt returns 423 lockout
    _find_input(at_fail, "Email").input("dave@example.com")
    _find_input(at_fail, "Password").input("DaveSuperStrongPassword1!")
    _find_button(at_fail, "Log in").click().run()
    assert "Too many attempts. Try again in 15 minutes." in _all_text(at_fail)


def test_forgot_and_reset_pages_end_to_end_and_expired_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-7, US-5: Forgot returns uniform reply; reset updates password and clears session."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)
    sent: list[dict[str, str]] = []
    monkeypatch.setattr(
        "opentrade.services.auth.send_email",
        lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}),
    )

    at_reg = _new_app(db_path, "register")
    _find_input(at_reg, "Name").input("Eve")
    _find_input(at_reg, "Email").input("eve@example.com")
    _find_input(at_reg, "Password").input("EveOriginalPassword99!")
    _find_input(at_reg, "Confirm password").input("EveOriginalPassword99!")
    _find_button(at_reg, "Create account").click().run()

    # Unknown email on forgot returns identical anti-enumeration text
    at_unknown = _new_app(db_path, "forgot")
    _find_input(at_unknown, "Email").input("nobody@example.com")
    _find_button(at_unknown, "Send reset link").click().run()
    assert "If an account exists for that email, we sent a reset link." in _all_text(at_unknown)

    # Known email on forgot returns identical text and sends reset token
    at_known = _new_app(db_path, "forgot")
    _find_input(at_known, "Email").input("eve@example.com")
    _find_button(at_known, "Send reset link").click().run()
    assert "If an account exists for that email, we sent a reset link." in _all_text(at_known)
    reset_token = _extract_token(sent[-1]["body"])

    # Weak password rejected on reset without consuming token
    at_reset = _new_app(db_path, "reset")
    at_reset.session_state["user"] = {"email": "eve@example.com", "verified": True}
    _find_input(at_reset, "Reset token").input(reset_token)
    _find_input(at_reset, "New password").input("weak")
    _find_input(at_reset, "Confirm new password").input("weak")
    _find_button(at_reset, "Reset password").click().run()
    assert len(at_reset.error) > 0

    # Valid reset clears authenticated user state
    _find_input(at_reset, "Reset token").input(reset_token)
    _find_input(at_reset, "New password").input("EveUpdatedPassword2026!")
    _find_input(at_reset, "Confirm new password").input("EveUpdatedPassword2026!")
    _find_button(at_reset, "Reset password").click().run()
    assert not at_reset.exception
    assert at_reset.session_state["user"] is None
    assert len(at_reset.success) > 0

    # Reusing consumed token displays expired/invalid prompt
    at_expired = _new_app(db_path, "reset")
    _find_input(at_expired, "Reset token").input(reset_token)
    _find_input(at_expired, "New password").input("EveThirdPassword2026!")
    _find_input(at_expired, "Confirm new password").input("EveThirdPassword2026!")
    _find_button(at_expired, "Reset password").click().run()
    assert "This link has expired. Request a new one." in _all_text(at_expired)
