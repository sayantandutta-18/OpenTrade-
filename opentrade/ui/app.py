"""Streamlit application entry point and page router."""

import streamlit as st

from opentrade.config import Provenance
from opentrade.ui.components.badge import (
    DEMO_MODE_BANNER_TEXT,
    render_prototype_banner,
    render_provenance_badge,
)
from opentrade.ui.pages.auth_pages import (
    render_forgot_page,
    render_login_page,
    render_register_page,
    render_reset_page,
    render_verify_page,
)
from opentrade.ui.pages.home import render_home_page
from opentrade.ui.state import (
    DEMO_SEED_KEY,
    FORGOT_PAGE,
    HOME_PAGE,
    LOGIN_PAGE,
    MODE_KEY,
    PAGE_KEY,
    REGISTER_PAGE,
    RESET_PAGE,
    SIMULATOR_PAGE,
    USER_KEY,
    VERIFY_PAGE,
    init_session_state,
    navigate_to,
)
from opentrade.ui.theme import apply_theme


def _render_simulator_placeholder() -> None:
    """Render the simulator landing state until Phase 1+ simulator UI."""
    user = st.session_state.get(USER_KEY)
    if user is None:
        st.info(DEMO_MODE_BANNER_TEXT)
    elif not user.get("verified"):
        st.warning("Verify your email to save runs")
        st.button("Verify email", on_click=navigate_to, args=(VERIFY_PAGE,))

    st.header("Simulator")
    seed = st.session_state.get(DEMO_SEED_KEY, 42)
    mode = st.session_state.get(MODE_KEY, "DEMO")
    render_provenance_badge(Provenance.SYNTHETIC, mode=str(mode))
    st.markdown(f"Active simulation seed: `{seed}`")
    st.button("Back to Home", on_click=navigate_to, args=(HOME_PAGE,))


def main() -> None:
    """Configure Streamlit app, render global prototype banner, and route pages."""
    st.set_page_config(page_title="OpenTrade", layout="centered")
    apply_theme()
    init_session_state()

    # AC-42 / FR-53: Prototype banner renders at the top of every page.
    render_prototype_banner()

    routes = {
        HOME_PAGE: render_home_page,
        REGISTER_PAGE: render_register_page,
        LOGIN_PAGE: render_login_page,
        VERIFY_PAGE: render_verify_page,
        FORGOT_PAGE: render_forgot_page,
        RESET_PAGE: render_reset_page,
        SIMULATOR_PAGE: _render_simulator_placeholder,
    }
    renderer = routes.get(st.session_state[PAGE_KEY], render_home_page)
    renderer()


if __name__ == "__main__":
    main()
