"""Company universe map, search, presets, and 6-company comparison basket (T5.1)."""

import streamlit as st

from opentrade.config import Provenance
from opentrade.services.catalog import (
    MAX_COMPARE,
    VALID_SECTORS,
    ComparisonSet,
    get_map_pins,
    load_presets,
    search_companies,
)
from opentrade.services.errors import CompareLimitError, ValidationError
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import (
    COMPARE_SYMBOLS_KEY,
    HOME_PAGE,
    PROFILES_PAGE,
    navigate_to,
)


def render_universe_map_page() -> None:
    """Render interactive Universe Map, search, presets, and comparison basket (T5.1)."""
    st.header("Universe Map")
    render_provenance_badge(Provenance.REAL)
    st.caption("Company catalog sourced from Public Exchange Filings (2026-01-15).")

    selected: list[str] = list(st.session_state.get(COMPARE_SYMBOLS_KEY, []))
    basket = ComparisonSet(symbols=selected)

    st.subheader(f"Comparison set: {len(basket.symbols)} of {MAX_COMPARE} selected")
    if basket.symbols:
        cols = st.columns(len(basket.symbols))
        for idx, sym in enumerate(basket.symbols):
            with cols[idx]:
                if st.button(f"Remove {sym}", key=f"rm_{sym}"):
                    basket.remove(sym)
                    st.session_state[COMPARE_SYMBOLS_KEY] = basket.symbols
                    st.rerun()

    add_col, btn_col = st.columns([3, 1])
    with add_col:
        symbol_to_add = st.text_input("Add company symbol", key="map_add_symbol")
    with btn_col:
        if st.button("Add symbol"):
            try:
                basket.add(symbol_to_add)
                st.session_state[COMPARE_SYMBOLS_KEY] = basket.symbols
                st.rerun()
            except CompareLimitError as err:
                st.warning(err.message)
            except ValidationError as err:
                st.error(err.message)

    presets = load_presets()
    preset_names = {p.id: p.name for p in presets}
    p_col, p_btn_col = st.columns([3, 1])
    with p_col:
        selected_preset = st.selectbox(
            "Preset basket",
            options=[p.id for p in presets],
            format_func=lambda pid: preset_names.get(pid, pid),
            key="map_preset_select",
        )
    with p_btn_col:
        if st.button("Load preset"):
            basket.load_preset(selected_preset)
            st.session_state[COMPARE_SYMBOLS_KEY] = basket.symbols
            st.rerun()

    st.divider()
    f1, f2, f3 = st.columns(3)
    with f1:
        query = st.text_input("Search companies", key="map_search_q")
    with f2:
        sector = str(
            st.selectbox("Sector", options=["All", *VALID_SECTORS], index=0, key="map_sector")
        )
    with f3:
        region = st.text_input("Region / country", key="map_region")

    sector_filter = None if sector == "All" else sector
    matches = search_companies(query=query, sector=sector_filter, region=region)
    pins = get_map_pins(sector=sector_filter)

    if pins:
        st.map({"lat": [p["lat"] for p in pins], "lon": [p["lon"] for p in pins]})
        st.caption(f"Showing {len(pins)} company pins | Provenance: REAL")

    st.subheader(f"Search matches ({len(matches)})")
    if matches:
        rows = [
            {
                "symbol": c.symbol,
                "name": c.name,
                "sector": c.sector,
                "hq": f"{c.hq_city}, {c.hq_country}",
                "market_cap_usd_bn": c.market_cap_usd_bn,
                "source": c.source,
                "date": c.source_date,
            }
            for c in matches
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("Open Profiles & Radar", on_click=navigate_to, args=(PROFILES_PAGE,))
    with nav2:
        st.button("Back to Home", key="map_home", on_click=navigate_to, args=(HOME_PAGE,))
