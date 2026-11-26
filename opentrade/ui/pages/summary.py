"""About / Summary page explaining methodology, provenance labels, and disclaimers (T20.2)."""

import streamlit as st

from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import HOME_PAGE, navigate_to


def render_summary_page() -> None:
    """Render About OpenTrade methodology and provenance documentation."""
    st.title("About OpenTrade")
    st.caption("Methodology, data provenance labels, and non-advisory research scope.")

    for label in ("REAL", "CALIBRATED", "SYNTHETIC", "DEMO", "LIVE"):
        render_provenance_badge(label)

    st.markdown(
        "**Methodology**\n"
        "- **Order Book & Matching**: Price-time priority limit order book "
        "with deterministic seeded order flow.\n"
        "- **Impact & Decay**: Square-root impact model with exponential post-trade decay.\n"
        "- **Provenance**: Every number is labeled `REAL`, `CALIBRATED`, "
        "`SYNTHETIC`, `DEMO`, or `LIVE`.\n"
        "- **Non-Advisory Guardrail**: OpenTrade refuses personalized buy/sell recommendations."
    )
    st.warning("Prototype. Not investment advice.")

    if st.button("Back to Home", key="summary_back_home"):
        navigate_to(HOME_PAGE)
