"""Guided Tour page introducing OpenTrade workflows and provenance rules (T20.2)."""

import streamlit as st

from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import (
    ANALYST_PAGE,
    HOME_PAGE,
    IMPACT_LAB_PAGE,
    SIMULATOR_PAGE,
    navigate_to,
)


def render_tour_page() -> None:
    """Render the Guided Tour page with explicit provenance badges and disclaimers."""
    st.title("Guided Tour")
    st.caption("Walkthrough of OpenTrade's market simulation and research tools.")
    render_provenance_badge("DEMO")

    st.markdown(
        "1. **Order Book Simulator**: Inspect synthetic limit order book "
        "depth, spread, and queue dynamics.\n"
        "2. **Impact Lab**: Measure temporary and permanent market impact "
        "with deterministic seed fingerprints.\n"
        "3. **Universe & Correlation**: Compare equities, liquidity profiles, "
        "and effective holdings.\n"
        "4. **AI Analyst**: Review grounded commentary with strict non-advisory guardrails."
    )
    st.info(
        "Prototype. Not investment advice. Simulated results do not predict real market outcomes."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Open Simulator", key="tour_sim_btn"):
            navigate_to(SIMULATOR_PAGE)
    with col2:
        if st.button("Open Impact Lab", key="tour_impact_btn"):
            navigate_to(IMPACT_LAB_PAGE)
    with col3:
        if st.button("Open AI Analyst", key="tour_analyst_btn"):
            navigate_to(ANALYST_PAGE)
    with col4:
        if st.button("Back to Home", key="tour_home_btn"):
            navigate_to(HOME_PAGE)
