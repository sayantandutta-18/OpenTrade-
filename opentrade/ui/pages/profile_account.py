"""Account & Profile page displaying signed-in user status and sign-out."""

import streamlit as st

from opentrade.ui.state import (
    LOGIN_PAGE,
    REGISTER_PAGE,
    USER_KEY,
    clear_authenticated_user,
    navigate_to,
)


def render_profile_account_page() -> None:
    """Render account profile summary or login/register actions."""
    st.title("Account & Profile")
    st.caption("Manage your OpenTrade session. Prototype. Not investment advice.")

    user = st.session_state.get(USER_KEY)
    if isinstance(user, dict) and "email" in user:
        st.markdown(f"**Name:** {user.get('name', 'User')}")
        st.markdown(f"**Email:** {user.get('email')}")
        verified = "Verified" if user.get("is_verified") else "Pending verification"
        st.markdown(f"**Status:** {verified}")
        if st.button("Sign out", key="account_signout_btn"):
            clear_authenticated_user()
            st.info("Signed out.")
    else:
        st.info("You are currently browsing in Demo / Guest mode.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Log in", key="account_login_btn"):
                navigate_to(LOGIN_PAGE)
        with col2:
            if st.button("Register", key="account_register_btn"):
                navigate_to(REGISTER_PAGE)
