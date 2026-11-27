"""Reusable chat panel component with advice guardrails and action confirmation (T22.1-T22.3)."""

from typing import Any

import streamlit as st

from opentrade.services.chat import (
    chat_turn_db_path,
    clear_chat_db_path,
    get_chat_history_db_path,
)
from opentrade.services.errors import AppError
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import MODE_KEY, USER_KEY, get_db_path


def render_chat_panel(
    screen_context: dict[str, Any] | None = None,
    key_prefix: str = "chat_panel",
) -> None:
    """Render the OpenTrade AI Assistant / Chat Panel (AC-37 to AC-40)."""
    st.subheader("Research Assistant Chat")
    mode = str(st.session_state.get(MODE_KEY, "DEMO"))
    render_provenance_badge("DEMO" if mode == "DEMO" else "LIVE")
    st.caption(
        "Ask about simulation metrics, provenance, or correlation. "
        "Prototype. Not investment advice."
    )

    user = st.session_state.get(USER_KEY)
    user_id = int(user["id"]) if isinstance(user, dict) and "id" in user else None
    db_path = get_db_path()

    if "chat_session_messages" not in st.session_state:
        st.session_state["chat_session_messages"] = []

    if user_id is not None:
        try:
            history = get_chat_history_db_path(db_path, user_id)
        except AppError:
            history = []
    else:
        history = list(st.session_state["chat_session_messages"])

    for msg in history:
        role_label = "You" if msg["role"] == "user" else "Assistant"
        st.markdown(f"**{role_label}:** {msg['content']}")

    prompt = st.text_input("Ask OpenTrade Assistant", key=f"{key_prefix}_input")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Send Message", key=f"{key_prefix}_send") and prompt.strip():
            try:
                reply = chat_turn_db_path(
                    db_path=db_path,
                    user_id=user_id,
                    message=prompt.strip(),
                    screen_context=screen_context or {},
                )
                if user_id is None:
                    st.session_state["chat_session_messages"].append(
                        {"role": "user", "content": prompt.strip()}
                    )
                    st.session_state["chat_session_messages"].append(
                        {"role": "assistant", "content": reply}
                    )
                else:
                    st.markdown(f"**Assistant:** {reply}")
            except AppError as exc:
                st.error(exc.message)
    with col2:
        if st.button("Clear Chat History", key=f"{key_prefix}_clear"):
            if user_id is not None:
                clear_chat_db_path(db_path, user_id)
            st.session_state["chat_session_messages"] = []
            st.info("Chat history cleared.")
