"""Company comparison matrix page (up to 6 companies)."""

import streamlit as st

from opentrade.services.catalog import load_catalog
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import COMPARE_SYMBOLS_KEY, UNIVERSE_MAP_PAGE, navigate_to


def render_compare_page() -> None:
    """Render side-by-side comparison table for selected companies."""
    st.title("Compare Companies")
    st.caption("Compare up to 6 selected companies. Prototype. Not investment advice.")
    render_provenance_badge("REAL")

    selected = list(st.session_state.get(COMPARE_SYMBOLS_KEY, []))
    if not selected:
        st.info("No companies selected yet. Pick companies on the Universe Map.")
        if st.button("Open Universe Map", key="compare_go_map"):
            navigate_to(UNIVERSE_MAP_PAGE)
        return

    catalog = {c.symbol: c for c in load_catalog()}
    rows = []
    for sym in selected[:6]:
        c = catalog.get(sym)
        if c:
            rows.append(
                {
                    "Symbol": c.symbol,
                    "Name": c.name,
                    "Sector": c.sector,
                    "Country": c.hq_country,
                    "Market Cap ($B)": c.market_cap_usd_bn,
                    "Source": c.source,
                }
            )
    st.dataframe(rows, use_container_width=True)
