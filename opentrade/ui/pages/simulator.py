"""Order book simulator screen (T3.5)."""

import streamlit as st

from opentrade.services.simulator import list_available_profiles, preview_book_and_inject
from opentrade.ui.components.badge import DEMO_MODE_BANNER_TEXT, render_provenance_badge
from opentrade.ui.state import (
    DEMO_SEED_KEY,
    HOME_PAGE,
    IMPACT_LAB_PAGE,
    MODE_KEY,
    USER_KEY,
    VERIFY_PAGE,
    navigate_to,
)


def _render_account_banner() -> None:
    """Render demo or email-verification status banner per USER_FLOW.md."""
    user = st.session_state.get(USER_KEY)
    if user is None:
        st.info(DEMO_MODE_BANNER_TEXT)
    elif not user.get("verified"):
        st.warning("Verify your email to save runs")
        st.button("Verify email", key="sim_verify_btn", on_click=navigate_to, args=(VERIFY_PAGE,))


def render_simulator_page() -> None:
    """Render interactive order book simulator with ladder, depth chart, and injection (T3.5)."""
    _render_account_banner()
    st.header("Simulator")

    profiles = list_available_profiles()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        profile_id = st.selectbox("Profile", options=profiles, index=0, key="sim_profile")
    with col2:
        seed = int(
            st.number_input(
                "Seed",
                min_value=0,
                max_value=999_999,
                value=int(st.session_state.get(DEMO_SEED_KEY, 42)),
                step=1,
                key="sim_seed",
            )
        )
    with col3:
        side = str(st.selectbox("Side", options=["BUY", "SELL"], index=0, key="sim_side"))
    with col4:
        qty = int(
            st.number_input("Order size", min_value=1, max_value=50_000, value=400, key="sim_qty")
        )

    if st.button("Inject order", type="primary"):
        st.session_state["sim_last_snapshot"] = preview_book_and_inject(
            profile_id=profile_id,
            seed=seed,
            side=side,
            qty=qty,
        )

    snap = st.session_state.get("sim_last_snapshot")
    if snap is None or snap.get("profile_id") != profile_id:
        snap = preview_book_and_inject(profile_id=profile_id, seed=seed, side=side, qty=0)

    mode = str(st.session_state.get(MODE_KEY, "DEMO"))
    render_provenance_badge(snap["provenance"], mode=mode)

    m1, m2, m3 = st.columns(3)
    m1.metric("Best bid (ticks)", str(snap["best_bid"]))
    m2.metric("Best ask (ticks)", str(snap["best_ask"]))
    m3.metric("Spread (ticks)", str(snap["spread_ticks"]))

    inj = snap.get("injection")
    if inj is not None:
        st.subheader("Last market order injection")
        render_provenance_badge(snap["provenance"], mode=mode)
        c1, c2, c3 = st.columns(3)
        c1.metric("Filled qty", str(inj["filled_qty"]))
        c2.metric("Avg fill (ticks)", f"{inj['avg_fill_price_ticks']:.2f}")
        c3.metric(
            "Slippage (bps)",
            f"{inj['slippage_bps']:.2f} bps",
            help="Extra cost compared with the mid price, in basis points.",
        )

    st.subheader("Resting book ladder & depth")
    bids_rows = snap["bids"]
    asks_rows = snap["asks"]
    if bids_rows or asks_rows:
        chart_rows = [
            {"price_ticks": r["price_ticks"], "bid_qty": r["qty"], "ask_qty": 0} for r in bids_rows
        ] + [
            {"price_ticks": r["price_ticks"], "bid_qty": 0, "ask_qty": r["qty"]} for r in asks_rows
        ]
        chart_rows.sort(key=lambda r: r["price_ticks"])
        st.bar_chart(
            {
                "price_ticks": [r["price_ticks"] for r in chart_rows],
                "bid_qty": [r["bid_qty"] for r in chart_rows],
                "ask_qty": [r["ask_qty"] for r in chart_rows],
            },
            x="price_ticks",
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption(f"Top bids ({snap['provenance']})")
        st.dataframe(bids_rows, use_container_width=True, hide_index=True)
    with col_b:
        st.caption(f"Top asks ({snap['provenance']})")
        st.dataframe(asks_rows, use_container_width=True, hide_index=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("Open impact lab", on_click=navigate_to, args=(IMPACT_LAB_PAGE,))
    with nav2:
        st.button("Back to Home", key="sim_home", on_click=navigate_to, args=(HOME_PAGE,))
