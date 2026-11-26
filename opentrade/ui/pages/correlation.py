"""Correlation overview and concentration-vs-count screens (T14.2)."""

import streamlit as st

from opentrade.services.correlation import analyze_correlation
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import (
    COMPARE_SYMBOLS_KEY,
    HOME_PAGE,
    UNIVERSE_MAP_PAGE,
    navigate_to,
)


def render_correlation_page() -> None:
    """Render correlation matrix, diversification verdict, and concentration curve (T14.2)."""
    st.header("Correlation & Diversification")

    selected = list(st.session_state.get(COMPARE_SYMBOLS_KEY, [])) or [
        "AAPL",
        "MSFT",
        "JPM",
        "XOM",
    ]
    analysis = analyze_correlation(selected)
    render_provenance_badge(analysis["label"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Verdict", str(analysis["verdict"]))
    c2.metric("Avg pairwise corr", f"{analysis['avg_correlation']:.2f}")
    c3.metric("Effective holdings", f"{analysis['effective_holdings']:.2f}")
    c4.metric("Nominal holdings", str(analysis["nominal_holdings"]))
    st.caption(
        "In this simulation, effective holdings equals 1 / sum(w_i^2) " f"[{analysis['label']}]."
    )

    st.subheader("Return correlation matrix")
    syms = analysis["symbols"]
    matrix_rows = []
    for idx, sym in enumerate(syms):
        row: dict[str, str | float] = {"symbol": sym}
        for col_idx, col_sym in enumerate(syms):
            row[col_sym] = analysis["matrix"][idx][col_idx]
        matrix_rows.append(row)
    st.dataframe(matrix_rows, use_container_width=True, hide_index=True)

    st.subheader("Concentration vs. nominal holding count")
    curve = analysis["concentration_curve"]
    if curve:
        st.line_chart(
            {
                "nominal_n": [pt["nominal_n"] for pt in curve],
                "effective_n": [pt["effective_n"] for pt in curve],
            },
            x="nominal_n",
        )
        st.caption(
            f"X-axis: nominal holdings N | Y-axis: effective independent holdings | "
            f"{analysis['label']}"
        )

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("Back to Universe Map", on_click=navigate_to, args=(UNIVERSE_MAP_PAGE,))
    with nav2:
        st.button("Back to Home", key="corr_home", on_click=navigate_to, args=(HOME_PAGE,))
