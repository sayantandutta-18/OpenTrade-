"""Execution Lab page comparing TWAP, VWAP, POV, and Almgren-Chriss IS (T13.1)."""

import streamlit as st

from opentrade.services.simulator import (
    list_available_profiles,
    run_execution_comparison_service,
)
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import DEMO_SEED_KEY


def render_execution_lab_page() -> None:
    """Render execution strategy shortfall comparison."""
    st.title("Execution Lab")
    st.caption(
        "Benchmark TWAP, VWAP, POV, and Implementation Shortfall. "
        "Prototype. Not investment advice."
    )
    render_provenance_badge("SYNTHETIC")

    profiles = list_available_profiles()
    profile_id = st.selectbox("Liquidity Profile", options=profiles, key="exec_lab_profile")
    qty = int(st.number_input("Parent Order Qty", min_value=50, max_value=5000, value=500))
    seed = int(st.session_state.get(DEMO_SEED_KEY, 42))

    res = run_execution_comparison_service(profile_id=str(profile_id), total_qty=qty, seed=seed)
    st.dataframe(res["rankings"], use_container_width=True)
