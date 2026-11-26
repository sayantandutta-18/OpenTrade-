"""Streamlit application entry point and page router."""

import streamlit as st

from opentrade.ui.components.badge import render_prototype_banner
from opentrade.ui.pages.analyst import render_analyst_page
from opentrade.ui.pages.auth_pages import (
    render_forgot_page,
    render_login_page,
    render_register_page,
    render_reset_page,
    render_verify_page,
)
from opentrade.ui.pages.correlation import render_correlation_page
from opentrade.ui.pages.home import render_home_page
from opentrade.ui.pages.impact_lab import render_impact_lab_page
from opentrade.ui.pages.market_data import render_market_data_page
from opentrade.ui.pages.news_lab import render_news_lab_page
from opentrade.ui.pages.profiles import render_profiles_page
from opentrade.ui.pages.run_history import render_run_history_page
from opentrade.ui.pages.simulator import render_simulator_page
from opentrade.ui.pages.summary import render_summary_page
from opentrade.ui.pages.tour import render_tour_page
from opentrade.ui.pages.universe_map import render_universe_map_page
from opentrade.ui.pages.validation import render_validation_page
from opentrade.ui.state import (
    ANALYST_PAGE,
    CORRELATION_PAGE,
    FORGOT_PAGE,
    HOME_PAGE,
    IMPACT_LAB_PAGE,
    LOGIN_PAGE,
    MARKET_DATA_PAGE,
    NEWS_LAB_PAGE,
    PAGE_KEY,
    PROFILES_PAGE,
    REGISTER_PAGE,
    RESET_PAGE,
    RUN_HISTORY_PAGE,
    SIMULATOR_PAGE,
    SUMMARY_PAGE,
    TOUR_PAGE,
    UNIVERSE_MAP_PAGE,
    VALIDATION_PAGE,
    VERIFY_PAGE,
    init_session_state,
)
from opentrade.ui.theme import apply_theme


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
        SIMULATOR_PAGE: render_simulator_page,
        IMPACT_LAB_PAGE: render_impact_lab_page,
        UNIVERSE_MAP_PAGE: render_universe_map_page,
        PROFILES_PAGE: render_profiles_page,
        MARKET_DATA_PAGE: render_market_data_page,
        NEWS_LAB_PAGE: render_news_lab_page,
        CORRELATION_PAGE: render_correlation_page,
        ANALYST_PAGE: render_analyst_page,
        RUN_HISTORY_PAGE: render_run_history_page,
        TOUR_PAGE: render_tour_page,
        SUMMARY_PAGE: render_summary_page,
        VALIDATION_PAGE: render_validation_page,
    }
    renderer = routes.get(st.session_state[PAGE_KEY], render_home_page)
    renderer()


if __name__ == "__main__":
    main()
