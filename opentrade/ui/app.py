"""Streamlit application entry point, sidebar navigation, and page router."""

from collections.abc import Callable

import streamlit as st

from opentrade.ui.components.badge import render_prototype_banner
from opentrade.ui.components.chat_panel import render_chat_panel
from opentrade.ui.pages.analyst import render_analyst_page
from opentrade.ui.pages.auth_pages import (
    render_forgot_page,
    render_login_page,
    render_register_page,
    render_reset_page,
    render_verify_page,
)
from opentrade.ui.pages.compare import render_compare_page
from opentrade.ui.pages.correlation import render_correlation_page
from opentrade.ui.pages.cross_impact import render_cross_impact_page
from opentrade.ui.pages.execution_lab import render_execution_lab_page
from opentrade.ui.pages.home import render_home_page
from opentrade.ui.pages.impact_lab import render_impact_lab_page
from opentrade.ui.pages.market_data import render_market_data_page
from opentrade.ui.pages.news_lab import render_news_lab_page
from opentrade.ui.pages.profile_account import render_profile_account_page
from opentrade.ui.pages.profiles import render_profiles_page
from opentrade.ui.pages.run_history import render_run_history_page
from opentrade.ui.pages.simulator import render_simulator_page
from opentrade.ui.pages.subscription import render_subscription_page
from opentrade.ui.pages.summary import render_summary_page
from opentrade.ui.pages.terms import render_terms_page
from opentrade.ui.pages.tour import render_tour_page
from opentrade.ui.pages.universe_map import render_universe_map_page
from opentrade.ui.pages.validation import render_validation_page
from opentrade.ui.state import (
    ANALYST_PAGE,
    COMPARE_PAGE,
    CORRELATION_PAGE,
    CROSS_IMPACT_PAGE,
    EXECUTION_LAB_PAGE,
    FORGOT_PAGE,
    HOME_PAGE,
    IMPACT_LAB_PAGE,
    LOGIN_PAGE,
    MARKET_DATA_PAGE,
    NEWS_LAB_PAGE,
    PAGE_KEY,
    PROFILE_ACCOUNT_PAGE,
    PROFILES_PAGE,
    REGISTER_PAGE,
    RESET_PAGE,
    RUN_HISTORY_PAGE,
    SIMULATOR_PAGE,
    SUBSCRIPTION_PAGE,
    SUMMARY_PAGE,
    TERMS_PAGE,
    TOUR_PAGE,
    UNIVERSE_MAP_PAGE,
    VALIDATION_PAGE,
    VERIFY_PAGE,
    init_session_state,
)
from opentrade.ui.theme import apply_theme

_PAGE_ITEMS: tuple[tuple[str, str, Callable[[], None]], ...] = (
    (HOME_PAGE, "Home", render_home_page),
    (SIMULATOR_PAGE, "Simulator", render_simulator_page),
    (IMPACT_LAB_PAGE, "Impact Lab", render_impact_lab_page),
    (EXECUTION_LAB_PAGE, "Execution Lab", render_execution_lab_page),
    (CROSS_IMPACT_PAGE, "Cross Impact", render_cross_impact_page),
    (CORRELATION_PAGE, "Correlation", render_correlation_page),
    (UNIVERSE_MAP_PAGE, "Universe Map", render_universe_map_page),
    (PROFILES_PAGE, "Profiles & Radar", render_profiles_page),
    (COMPARE_PAGE, "Compare", render_compare_page),
    (MARKET_DATA_PAGE, "Market Data", render_market_data_page),
    (NEWS_LAB_PAGE, "News Lab", render_news_lab_page),
    (ANALYST_PAGE, "AI Analyst", render_analyst_page),
    (RUN_HISTORY_PAGE, "Run History", render_run_history_page),
    (VALIDATION_PAGE, "Validation", render_validation_page),
    (TOUR_PAGE, "Guided Tour", render_tour_page),
    (SUMMARY_PAGE, "About / Summary", render_summary_page),
    (PROFILE_ACCOUNT_PAGE, "Profile / Account", render_profile_account_page),
    (SUBSCRIPTION_PAGE, "Subscription (INR ₹)", render_subscription_page),
    (TERMS_PAGE, "Terms & Conditions", render_terms_page),
    (LOGIN_PAGE, "Log in", render_login_page),
    (REGISTER_PAGE, "Register", render_register_page),
    (VERIFY_PAGE, "Verify Email", render_verify_page),
    (FORGOT_PAGE, "Forgot Password", render_forgot_page),
    (RESET_PAGE, "Reset Password", render_reset_page),
)


def _on_sidebar_nav_change() -> None:
    """Sync sidebar navigation selection into centralized PAGE_KEY."""
    selected = st.session_state.get("sidebar_nav_select")
    if isinstance(selected, str):
        st.session_state[PAGE_KEY] = selected


def main() -> None:
    """Configure Streamlit app, render global prototype banner, sidebar, and route pages."""
    st.set_page_config(page_title="OpenTrade", layout="centered")
    apply_theme()
    init_session_state()

    routes = {page_id: renderer for page_id, _, renderer in _PAGE_ITEMS}
    labels = {page_id: label for page_id, label, _ in _PAGE_ITEMS}
    page_ids = [page_id for page_id, _, _ in _PAGE_ITEMS]

    current_page = str(st.session_state.get(PAGE_KEY, HOME_PAGE))
    if current_page not in routes:
        current_page = HOME_PAGE
        st.session_state[PAGE_KEY] = HOME_PAGE

    with st.sidebar:
        st.title("OpenTrade")
        st.selectbox(
            "Navigation",
            options=page_ids,
            index=page_ids.index(current_page),
            format_func=lambda pid: labels.get(pid, pid),
            key="sidebar_nav_select",
            on_change=_on_sidebar_nav_change,
        )
        with st.expander("Research Assistant Chat", expanded=False):
            render_chat_panel(screen_context={"screen": current_page}, key_prefix="sidebar_chat")

    # AC-42 / FR-53: Prototype banner renders at the top of every page.
    render_prototype_banner()

    renderer = routes.get(st.session_state[PAGE_KEY], render_home_page)
    renderer()


if __name__ == "__main__":
    main()
