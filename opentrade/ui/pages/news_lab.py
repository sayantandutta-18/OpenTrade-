"""News feed and shock headlines panel with Demo/Live toggle (T8.2)."""

import streamlit as st

from opentrade.services.catalog import VALID_SECTORS
from opentrade.services.news import compare_calm_vs_news_slippage, get_news
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import DEMO_SEED_KEY, HOME_PAGE, MARKET_DATA_PAGE, navigate_to


def render_news_lab_page() -> None:
    """Render News Lab panel with Demo/Live toggle, filters, and sanitized headlines (T8.2)."""
    st.header("News Lab")

    col1, col2, col3 = st.columns(3)
    with col1:
        mode_choice = str(
            st.radio(
                "News mode", options=["Demo", "Live"], index=0, horizontal=True, key="news_mode"
            )
        )
    with col2:
        sym_raw = st.text_input("Filter symbols", value="", key="news_symbols")
    with col3:
        sector = str(
            st.selectbox("Sector", options=["All", *VALID_SECTORS], index=0, key="news_sector")
        )

    symbols = [s.strip().upper() for s in sym_raw.split(",") if s.strip()]
    sector_filter = None if sector == "All" else sector
    payload = get_news(symbols=symbols, mode=mode_choice.lower(), sector=sector_filter)

    render_provenance_badge(payload["mode"])
    if payload.get("fallback_reason"):
        st.warning(str(payload["fallback_reason"]))

    items = payload["items"]
    if not items:
        st.info("No headlines matched the current filter.")
    else:
        for item in items:
            st.subheader(str(item["title"]))
            st.caption(
                f"{item['source']} | {item['age']} ({item['published_at']}) | "
                f"Label: {item['label']}"
            )
            if item.get("summary"):
                st.markdown(str(item["summary"]))
            st.divider()

    st.subheader("Calm vs. News Shock Slippage")
    if st.button("Compare calm vs news", type="primary"):
        seed = int(st.session_state.get(DEMO_SEED_KEY, 42))
        st.session_state["news_slippage_comp"] = compare_calm_vs_news_slippage(seed=seed)

    comp = st.session_state.get("news_slippage_comp")
    if comp is not None:
        render_provenance_badge(comp["provenance"])
        c_calm, c_news = st.columns(2)
        c_calm.metric(
            "Calm slippage (mean)",
            f"{comp['calm']['mean_bps']:.2f} bps",
        )
        c_calm.caption(f"95% CI: {comp['calm']['ci95']}")
        c_news.metric(
            "News shock slippage (mean)",
            f"{comp['news']['mean_bps']:.2f} bps",
        )
        c_news.caption(f"95% CI: {comp['news']['ci95']}")

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("Back to Market Data", on_click=navigate_to, args=(MARKET_DATA_PAGE,))
    with nav2:
        st.button("Back to Home", key="news_home", on_click=navigate_to, args=(HOME_PAGE,))
