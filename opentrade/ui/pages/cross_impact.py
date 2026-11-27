"""Cross-Impact Lab page demonstrating coupled-book correlation emergence (T15.1)."""

import streamlit as st

from opentrade.services.simulator import run_cross_impact_service
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import DEMO_SEED_KEY


def render_cross_impact_page() -> None:
    """Render multi-book cross-impact simulation controls and emergent correlation."""
    st.title("Cross-Impact Lab")
    st.caption(
        "Explore how order flow in Book A induces return correlation in Book B. "
        "Prototype. Not investment advice."
    )
    render_provenance_badge("SYNTHETIC")

    beta = float(st.slider("Cross-Impact Coupling (beta)", min_value=0.0, max_value=1.5, value=0.8))
    steps = int(st.number_input("Simulation Steps", min_value=30, max_value=300, value=120))
    seed = int(st.session_state.get(DEMO_SEED_KEY, 42))

    res = run_cross_impact_service(steps=steps, cross_impact_beta=beta, seed=seed)
    st.metric("Emergent Pearson Correlation", f"{res['emergent_correlation']:.3f}")
