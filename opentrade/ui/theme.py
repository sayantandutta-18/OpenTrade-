"""UI colors, typography, and custom CSS styling per docs/UI_UX_GUIDELINES.md §3."""

import streamlit as st

DARK_THEME: dict[str, str] = {
    "background": "#0B0F17",
    "card": "#111827",
    "border": "#1F2937",
    "text_primary": "#E5E7EB",
    "text_secondary": "#9CA3AF",
    "accent": "#E8A33D",
    "positive": "#34D399",
    "negative": "#F87171",
    "info": "#5EEAD4",
}

LIGHT_THEME: dict[str, str] = {
    "background": "#F7F8FA",
    "card": "#FFFFFF",
    "border": "#E5E7EB",
    "text_primary": "#111827",
    "text_secondary": "#4B5563",
    "accent": "#B45309",
    "positive": "#047857",
    "negative": "#B91C1C",
    "info": "#0F766E",
}

_STATIC_THEME_CSS = """
<style>
.block-container {
    max-width: 720px;
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}
.stButton > button {
    min-height: 44px;
    min-width: 44px;
}
</style>
"""


def apply_theme() -> None:
    """Apply static layout and touch-target CSS per docs/UI_UX_GUIDELINES.md."""
    st.markdown(_STATIC_THEME_CSS, unsafe_allow_html=True)
