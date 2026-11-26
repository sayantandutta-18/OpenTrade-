"""Stylized-Fact Validation page displaying engine validation checks (T18.1)."""

import streamlit as st

from opentrade.services.simulator import list_available_profiles, run_validation_service
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import HOME_PAGE, navigate_to


def render_validation_page() -> None:
    """Render stylized-fact validation checks for simulated order flow."""
    st.title("Stylized-Fact Validation")
    st.caption(
        "Verify fat tails, volatility clustering, positive spreads, and signature plots. "
        "Prototype. Not investment advice."
    )
    render_provenance_badge("SYNTHETIC")

    if st.button("Back to Home", key="val_back_home"):
        navigate_to(HOME_PAGE)
        return

    profiles = list_available_profiles()
    profile_id = st.selectbox("Liquidity Profile", options=profiles, key="val_profile_select")
    seed = int(st.number_input("Seed", min_value=1, max_value=99999, value=42, key="val_seed"))

    res = run_validation_service(profile_id=str(profile_id), seed=seed, steps=300)
    status_text = "ALL CHECKS PASSED" if res["all_passed"] else "SOME CHECKS FAILED"
    st.markdown(f"**Status:** {status_text}")
    for chk in res["checks"]:
        badge = "PASS" if chk["passed"] else "FAIL"
        st.markdown(
            f"- **{chk['name']}**: `{badge}` "
            f"(value={chk['value']:.4f}, threshold={chk['threshold']})"
        )
