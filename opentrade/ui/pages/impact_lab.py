"""Market impact experiment lab screen (T3.6)."""

import math
from typing import Any

import streamlit as st

from opentrade.config import RunConfig
from opentrade.services.runs import save_impact_run_db_path
from opentrade.services.simulator import list_available_profiles
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import (
    DEMO_SEED_KEY,
    HOME_PAGE,
    LOGIN_PAGE,
    MODE_KEY,
    SIMULATOR_PAGE,
    USER_KEY,
    get_db_path,
    navigate_to,
)

DEFAULT_SIZES: tuple[int, ...] = (100, 300, 1000, 3000, 6000, 10000)


def _explain_exponent(beta: float, provenance: str) -> str:
    """Return plain-language impact exponent interpretation per AC-22."""
    shape = "concave (square-root-like)" if beta < 0.85 else "near-linear"
    return (
        f"In this simulation, the model shows slippage scales as size^{beta:.2f} "
        f"({shape} price impact) [{provenance}]."
    )


def _render_sweep_results(run_data: dict[str, Any], mode: str) -> None:
    """Render impact sweep chart, exponent CI, decay curve, and explanation."""
    results = run_data["results"]
    prov = str(run_data["provenance"])
    fit = results["fit"]
    decay = results["decay"]
    ci_low, ci_high = fit["ci95"]

    render_provenance_badge(prov, mode=mode)
    if results.get("book_capped"):
        st.info(f"Book depth capped at {results['max_available_depth']} units in this simulation.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Impact exponent (beta)", f"{fit['beta']:.3f}")
    c2.metric("95% CI", f"[{ci_low:.3f}, {ci_high:.3f}]")
    c3.metric("R-squared", f"{fit['r_squared']:.4f}")
    st.markdown(_explain_exponent(float(fit["beta"]), prov))

    st.subheader("Log-log market impact curve")
    sweep_rows = results["impact"]
    if sweep_rows:
        st.line_chart(
            {
                "log10_size": [math.log10(max(1, r["size"])) for r in sweep_rows],
                "log10_slippage_bps": [
                    math.log10(max(1e-6, r["slippage_bps"])) for r in sweep_rows
                ],
            },
            x="log10_size",
        )
        st.caption(f"X-axis: log10(order size) | Y-axis: log10(slippage bps) | {prov}")

    st.subheader("Impact decay (temporary vs. permanent)")
    d1, d2, d3 = st.columns(3)
    d1.metric("Peak impact", f"{decay['peak_impact_bps']:.2f} bps")
    d2.metric("Temporary impact", f"{decay['temporary_impact_bps']:.2f} bps")
    d3.metric("Permanent impact", f"{decay['permanent_impact_bps']:.2f} bps")

    decay_rows = decay["curve"]
    if decay_rows:
        st.line_chart(
            {
                "step": [r["step"] for r in decay_rows],
                "impact_bps": [r["impact_bps"] for r in decay_rows],
            },
            x="step",
        )
        st.caption(f"X-axis: post-trade steps | Y-axis: mid-price impact (bps) | {prov}")


def render_impact_lab_page() -> None:
    """Render Market Impact Lab for sweeps, power-law fits, decay, and saving runs (T3.6)."""
    st.header("Impact Lab")
    render_provenance_badge("SYNTHETIC", mode=str(st.session_state.get(MODE_KEY, "DEMO")))
    profiles = list_available_profiles()

    col1, col2, col3 = st.columns(3)
    with col1:
        profile_id = st.selectbox("Profile", options=profiles, index=0, key="lab_profile")
    with col2:
        seed = int(
            st.number_input(
                "Seed",
                min_value=0,
                max_value=999_999,
                value=int(st.session_state.get(DEMO_SEED_KEY, 42)),
                step=1,
                key="lab_seed",
            )
        )
    with col3:
        side = str(st.selectbox("Side", options=["BUY", "SELL"], index=0, key="lab_side"))

    run_name = st.text_input("Run name", value="Impact Sweep", key="lab_run_name")
    cfg = RunConfig(seed=seed, profile_id=profile_id, sizes=DEFAULT_SIZES, book_depth=15)

    if st.button("Run sweep", type="primary"):
        preview_run, _ = save_impact_run_db_path(
            db_path=None,
            user_id=None,
            is_verified=False,
            config=cfg,
            name=run_name or "Impact Sweep",
            side=side,
        )
        st.session_state["last_impact_run"] = preview_run

    run_data = st.session_state.get("last_impact_run")
    if run_data is not None:
        _render_sweep_results(run_data, mode=str(st.session_state.get(MODE_KEY, "DEMO")))

        if st.button("Save run"):
            user = st.session_state.get(USER_KEY)
            if user is None or not user.get("verified"):
                st.warning("Log in with a verified email to save runs.")
                st.button("Log in to save", on_click=navigate_to, args=(LOGIN_PAGE,))
            else:
                saved_run, was_saved = save_impact_run_db_path(
                    db_path=get_db_path(),
                    user_id=int(user["id"]),
                    is_verified=True,
                    config=cfg,
                    name=run_name or "Impact Sweep",
                    side=side,
                )
                if was_saved:
                    st.success(
                        f"Saved run {saved_run['id']} (fingerprint {saved_run['fingerprint']})"
                    )

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("Back to Simulator", on_click=navigate_to, args=(SIMULATOR_PAGE,))
    with nav2:
        st.button("Back to Home", key="lab_home", on_click=navigate_to, args=(HOME_PAGE,))
