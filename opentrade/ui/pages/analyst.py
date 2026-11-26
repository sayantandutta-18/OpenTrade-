"""AI Analyst screen with 4 fixed prompts, Demo/Live toggle, and chat panel (T16.2)."""

from typing import Any

import streamlit as st

from opentrade.services.analyst import ANALYST_PROMPTS, run_analyst_prompt
from opentrade.services.errors import AppError
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.components.chat_panel import render_chat_panel
from opentrade.ui.state import HOME_PAGE, MODE_KEY, navigate_to

_DEFAULT_CONTEXT: dict[str, Any] = {
    "provenance": "SYNTHETIC",
    "correlation": 0.42,
    "beta": 0.51,
    "spread_ticks": 2,
    "vwap_slippage_bps": 12.4,
    "top_region": "US",
    "factor_score": 0.78,
}


def render_analyst_page() -> None:
    """Render the AI Analyst page with 4 fixed prompts and Demo/Live switch (AC-34 to AC-36)."""
    st.title("AI Analyst")
    st.caption(
        "Structured research commentary grounded in verified simulation numbers. "
        "Prototype. Not investment advice."
    )

    if st.button("Back to Home", key="analyst_back_home"):
        navigate_to(HOME_PAGE)
        return

    mode_choice = st.radio(
        "Analyst Mode",
        options=["DEMO", "LIVE"],
        index=0 if st.session_state.get(MODE_KEY, "DEMO") == "DEMO" else 1,
        key="analyst_mode_radio",
        horizontal=True,
    )
    st.session_state[MODE_KEY] = mode_choice
    render_provenance_badge("DEMO" if mode_choice == "DEMO" else "LIVE")

    st.subheader("Select an Analysis Prompt")
    cols = st.columns(len(ANALYST_PROMPTS))
    for idx, prompt_id in enumerate(ANALYST_PROMPTS):
        with cols[idx]:
            if st.button(prompt_id, key=f"analyst_btn_{prompt_id}"):
                st.session_state["selected_analyst_prompt"] = prompt_id

    selected = st.session_state.get("selected_analyst_prompt")
    if selected in ANALYST_PROMPTS:
        try:
            res = run_analyst_prompt(
                prompt_id=str(selected),
                mode=mode_choice,
                context_data=_DEFAULT_CONTEXT,
            )
            render_provenance_badge(str(res["provenance"]))
            st.markdown(f"**Prompt:** {res['prompt_id']} | **Mode:** {res['mode']}")
            st.markdown(str(res["answer"]))
            if res.get("unverified"):
                st.warning("Unverified response: numeric check flagged ungrounded numbers.")
        except AppError as exc:
            st.error(exc.message)

    st.divider()
    render_chat_panel(screen_context={"screen": "analyst", **_DEFAULT_CONTEXT})
