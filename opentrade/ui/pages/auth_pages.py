"""Authentication pages: register, login, verify, forgot, reset (T0.17)."""

from typing import Any

import streamlit as st

from opentrade.services.auth import (
    forgot_password_endpoint,
    login_endpoint,
    register_endpoint,
    resend_verification_endpoint,
    reset_password_endpoint,
    verify_email_endpoint,
)
from opentrade.ui.state import (
    FORGOT_PAGE,
    HOME_PAGE,
    LOGIN_PAGE,
    PENDING_EMAIL_KEY,
    REGISTER_PAGE,
    SIMULATOR_PAGE,
    clear_authenticated_user,
    get_db_path,
    navigate_to,
    set_authenticated_user,
)

PRIVACY_NOTE = "We store your name, email, and password (hashed). Nothing else."
RULES_HINT = (
    "Password rules: at least 12 characters (up to 128), not a common password, "
    "and not equal to your name or email."
)


def _error_message(payload: dict[str, Any], fallback: str) -> str:
    """Extract user-facing error message from an API error envelope."""
    err = payload.get("error")
    if isinstance(err, dict) and err.get("message"):
        return str(err["message"])
    return fallback


def render_register_page() -> None:
    """Render user registration screen with privacy note and password rules (AC-10, FR-1)."""
    st.header("Register")
    st.caption(RULES_HINT)

    name = st.text_input("Name", key="reg_name")
    email = st.text_input("Email", key="reg_email")
    password = st.text_input("Password", type="password", key="reg_password")
    confirm = st.text_input("Confirm password", type="password", key="reg_confirm")
    st.info(PRIVACY_NOTE)

    if st.button("Create account", type="primary"):
        if password != confirm:
            st.error("Passwords do not match.")
        else:
            status, payload = register_endpoint(
                {"name": name, "email": email, "password": password},
                db_path=get_db_path(),
            )
            if status == 201:
                clean_email = email.strip().lower()
                st.session_state[PENDING_EMAIL_KEY] = clean_email
                st.success(f"Check your inbox. We sent a link to {clean_email}.")
            else:
                st.error(_error_message(payload, "Registration failed. Check your inputs."))

    pending_email = st.session_state.get(PENDING_EMAIL_KEY, "")
    if pending_email and st.button("Resend link"):
        status, payload = resend_verification_endpoint(
            {"email": pending_email},
            db_path=get_db_path(),
        )
        if status == 202:
            st.info(str(payload.get("message", "Verification link sent.")))
        else:
            st.error(_error_message(payload, "Could not resend verification link."))

    col1, col2 = st.columns(2)
    with col1:
        st.button("Log in", key="reg_to_login", on_click=navigate_to, args=(LOGIN_PAGE,))
    with col2:
        st.button("Back to Home", key="reg_to_home", on_click=navigate_to, args=(HOME_PAGE,))


def render_login_page() -> None:
    """Render login screen with lockout and rate-limit feedback (FR-4, FR-5, US-3, US-4)."""
    st.header("Log in")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Log in", type="primary", key="login_submit"):
        result = login_endpoint(
            {"email": email, "password": password},
            db_path=get_db_path(),
        )
        if result.status_code == 200:
            user = result.body.get("user", {})
            set_authenticated_user(user, result.headers.get("Set-Cookie"))
            navigate_to(SIMULATOR_PAGE)
            st.rerun()
        elif result.status_code == 401:
            st.error("Email or password is incorrect.")
        elif result.status_code == 423:
            st.error("Too many attempts. Try again in 15 minutes.")
        else:
            st.error(_error_message(result.body, "Login failed."))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("Forgot password?", on_click=navigate_to, args=(FORGOT_PAGE,))
    with col2:
        st.button("Register", key="login_to_reg", on_click=navigate_to, args=(REGISTER_PAGE,))
    with col3:
        st.button("Back to Home", key="login_to_home", on_click=navigate_to, args=(HOME_PAGE,))


def render_verify_page() -> None:
    """Render email verification and resend screen (FR-3, US-2)."""
    st.header("Verify email")
    token = st.text_input("Verification token", key="verify_token")

    if st.button("Verify email", type="primary"):
        status, payload = verify_email_endpoint({"token": token}, db_path=get_db_path())
        if status == 200 and payload.get("verified"):
            st.success("Your email is confirmed.")
            st.session_state["email_verified_ui"] = True
        else:
            st.error(_error_message(payload, "Invalid or expired verification token."))

    if st.session_state.get("email_verified_ui"):
        st.button("Continue", on_click=navigate_to, args=(LOGIN_PAGE,))

    st.divider()
    resend_email = st.text_input(
        "Email for new link",
        value=st.session_state.get(PENDING_EMAIL_KEY, ""),
        key="verify_resend_email",
    )
    if st.button("Send a new link"):
        status, payload = resend_verification_endpoint(
            {"email": resend_email},
            db_path=get_db_path(),
        )
        if status == 202:
            st.success(str(payload.get("message", "A new verification link has been sent.")))
        else:
            st.error(_error_message(payload, "Could not send a new verification link."))

    st.button("Back to Home", key="verify_to_home", on_click=navigate_to, args=(HOME_PAGE,))


def render_forgot_page() -> None:
    """Render forgot-password request screen with anti-enumeration reply (FR-7, US-5)."""
    st.header("Forgot password")
    email = st.text_input("Email", key="forgot_email")

    if st.button("Send reset link", type="primary"):
        result = forgot_password_endpoint({"email": email}, db_path=get_db_path())
        if result.status_code == 202:
            st.info("If an account exists for that email, we sent a reset link.")
        else:
            st.error(_error_message(result.body, "Could not process reset request."))

    st.button("Back to Log in", key="forgot_to_login", on_click=navigate_to, args=(LOGIN_PAGE,))


def render_reset_page() -> None:
    """Render password reset screen enforcing password rules and session clear (FR-7, US-5)."""
    st.header("Reset password")
    st.caption(RULES_HINT)
    token = st.text_input("Reset token", key="reset_token")
    new_password = st.text_input("New password", type="password", key="reset_new_pw")
    confirm_password = st.text_input(
        "Confirm new password",
        type="password",
        key="reset_confirm_pw",
    )

    if st.button("Reset password", type="primary"):
        if new_password != confirm_password:
            st.error("Passwords do not match.")
        else:
            result = reset_password_endpoint(
                {"token": token, "new_password": new_password},
                db_path=get_db_path(),
            )
            if result.status_code == 204:
                clear_authenticated_user()
                st.success("Your password has been reset. Please log in.")
            elif result.status_code == 400:
                st.error("This link has expired. Request a new one.")
            else:
                st.error(_error_message(result.body, "Could not reset password."))

    st.button("Back to Log in", key="reset_to_login", on_click=navigate_to, args=(LOGIN_PAGE,))
