"""Prototype banner and provenance/mode badge components per UI_UX_GUIDELINES.md."""

import streamlit as st

from opentrade.config import Provenance

PROTOTYPE_BANNER_TEXT = "Prototype. Not investment advice."
DEMO_MODE_BANNER_TEXT = "Demo mode. Runs are not saved. Create an account to keep them."


def render_prototype_banner() -> None:
    """Render the mandatory top-of-page prototype disclaimer per AC-42 and FR-53."""
    st.caption(PROTOTYPE_BANNER_TEXT)
    st.divider()


def render_provenance_badge(label: Provenance | str, mode: str | None = None) -> None:
    """Render an explicit uppercase provenance (and optional mode) text badge per FR-52."""
    label_text = label.value if isinstance(label, Provenance) else str(label).strip().upper()
    if mode:
        mode_text = mode.strip().upper()
        st.caption(f"Provenance: {label_text} | Mode: {mode_text}")
    else:
        st.caption(f"Provenance: {label_text}")
