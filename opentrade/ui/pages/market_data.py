"""Market data quotes, 60-day history, and watchlist screen (T7.3)."""

import streamlit as st

from opentrade.services.catalog import load_catalog
from opentrade.services.market import get_history, get_quote, watchlist_action_db_path
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import (
    COMPARE_SYMBOLS_KEY,
    DEMO_WATCHLIST_KEY,
    HOME_PAGE,
    NEWS_LAB_PAGE,
    USER_KEY,
    get_db_path,
    navigate_to,
)


def render_market_data_page() -> None:
    """Render quote card, 60-day OHLCV chart, and per-user/demo watchlist (T7.3)."""
    st.header("Market Data")

    catalog_syms = [c.symbol for c in load_catalog()]
    selected_basket = list(st.session_state.get(COMPARE_SYMBOLS_KEY, []))
    options = selected_basket or catalog_syms[:20] or ["AAPL"]
    symbol = str(st.selectbox("Select symbol", options=options, index=0, key="mkt_symbol"))

    quote = get_quote(symbol)
    render_provenance_badge(quote["label"])
    if quote.get("reason"):
        st.caption(f"Source: {quote['source']} ({quote['reason']})")

    c1, c2, c3 = st.columns(3)
    c1.metric("Price", f"${quote['price']:.2f}")
    c2.metric("Change", f"{quote['change']:+.2f} ({quote['change_pct']:+.2f}%)")
    c3.metric("Prev close", f"${quote['prev_close']:.2f}")

    st.subheader("60-day price history")
    hist = get_history(symbol, days=60)
    render_provenance_badge(hist["label"])
    points = hist["points"]
    if points:
        st.line_chart(
            {
                "date": [p["date"] for p in points],
                "close": [p["close"] for p in points],
            },
            x="date",
        )
        st.caption(f"X-axis: date | Y-axis: close price | Provenance: {hist['label']}")

    st.divider()
    st.subheader("Watchlist")
    user = st.session_state.get(USER_KEY)

    col_add, col_rm = st.columns(2)
    add_clicked = col_add.button("Add to watchlist", type="primary")
    rm_clicked = col_rm.button("Remove from watchlist")

    if user is not None and bool(user.get("verified")):
        action = "add" if add_clicked else ("remove" if rm_clicked else "list")
        rows = watchlist_action_db_path(get_db_path(), int(user["id"]), action, symbol)
    else:
        demo_list: list[str] = list(st.session_state.get(DEMO_WATCHLIST_KEY, []))
        if add_clicked and symbol not in demo_list:
            demo_list.append(symbol)
        elif rm_clicked and symbol in demo_list:
            demo_list.remove(symbol)
        st.session_state[DEMO_WATCHLIST_KEY] = demo_list
        rows = [
            {
                "symbol": sym,
                "price": q["price"],
                "change_pct": q["change_pct"],
                "label": q["label"],
                "source": q["source"],
            }
            for sym in demo_list
            for q in [get_quote(sym)]
        ]
        st.caption("Demo mode: watchlist is kept for this session only.")

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Your watchlist is empty. Select a symbol above and click Add to watchlist.")

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("Open News Lab", on_click=navigate_to, args=(NEWS_LAB_PAGE,))
    with nav2:
        st.button("Back to Home", key="mkt_home", on_click=navigate_to, args=(HOME_PAGE,))
