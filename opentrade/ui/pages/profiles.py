"""Liquidity profiles and factor radar comparison page (T6.1-T6.2)."""

import streamlit as st

from opentrade.config import Provenance
from opentrade.services.profiles import (
    RADAR_FACTORS,
    load_calibrated_profiles,
    score_factor_radar,
)
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import (
    COMPARE_SYMBOLS_KEY,
    HOME_PAGE,
    UNIVERSE_MAP_PAGE,
    navigate_to,
)


def render_profiles_page() -> None:
    """Render calibrated liquidity profiles and factor radar with missing-value labels (AC-27)."""
    st.header("Liquidity Profiles & Factor Radar")
    render_provenance_badge(Provenance.CALIBRATED)

    selected = list(st.session_state.get(COMPARE_SYMBOLS_KEY, [])) or ["AAPL", "JPM", "TSLA"]
    calibrated = load_calibrated_profiles()
    radars = score_factor_radar(selected)

    st.subheader("Factor Radar (0-100 scale, CALIBRATED)")
    table_rows = []
    for radar in radars:
        row: dict[str, str] = {"symbol": radar.symbol, "provenance": radar.provenance.value}
        for factor in RADAR_FACTORS:
            val = radar.scores[factor]
            row[factor] = f"{val:.1f}" if val is not None else "missing"
        row["composite"] = (
            f"{radar.composite_score:.1f}" if radar.composite_score is not None else "missing"
        )
        table_rows.append(row)

    st.dataframe(table_rows, use_container_width=True, hide_index=True)
    st.caption("Traits without input are labeled 'missing' rather than zero or average (AC-27).")

    st.subheader("Calibrated microstructure profiles")
    prof_rows = []
    for sym in selected:
        prof = calibrated.get(sym.upper())
        if prof is not None:
            prof_rows.append(
                {
                    "symbol": prof.symbol,
                    "spread_bps": prof.typical_spread_bps,
                    "top_depth_shares": prof.top_depth_shares,
                    "arrival_rate_per_sec": prof.arrival_rate_per_sec,
                    "daily_volatility": prof.daily_volatility,
                    "source": prof.source,
                    "calibrated_at": prof.calibrated_at,
                    "provenance": prof.provenance.value,
                }
            )
    if prof_rows:
        st.dataframe(prof_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No calibrated microstructure profiles found for the selected symbols.")

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("Back to Universe Map", on_click=navigate_to, args=(UNIVERSE_MAP_PAGE,))
    with nav2:
        st.button("Back to Home", key="prof_home", on_click=navigate_to, args=(HOME_PAGE,))
