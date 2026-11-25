"""Home page with hero section, provenance labels, and entry actions (T0.16)."""

import streamlit as st

from opentrade.config import Provenance
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import (
    LOGIN_PAGE,
    REGISTER_PAGE,
    navigate_to,
    start_demo_mode,
)


def render_home_page() -> None:
    """Render the OpenTrade home screen with Demo, Log in, and Register actions."""
    st.title("OpenTrade")
    st.markdown(
        "Explore limit order book dynamics, market impact, and liquidity profiles "
        "in this simulation."
    )
    render_provenance_badge(Provenance.SYNTHETIC, mode="DEMO")

    st.subheader("Get started")
    col_demo, col_login, col_register = st.columns(3)
    with col_demo:
        st.button(
            "Start in demo mode",
            type="primary",
            use_container_width=True,
            on_click=start_demo_mode,
            kwargs={"seed": 42},
        )
    with col_login:
        st.button(
            "Log in",
            use_container_width=True,
            on_click=navigate_to,
            args=(LOGIN_PAGE,),
        )
    with col_register:
        st.button(
            "Register",
            use_container_width=True,
            on_click=navigate_to,
            args=(REGISTER_PAGE,),
        )
