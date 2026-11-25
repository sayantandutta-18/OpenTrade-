"""Centralized Streamlit session state keys and navigation helpers."""

from typing import Any

import streamlit as st

PAGE_KEY = "current_page"
MODE_KEY = "mode"
DEMO_SEED_KEY = "demo_seed"
USER_KEY = "user"
DB_PATH_KEY = "db_path"
PENDING_EMAIL_KEY = "pending_email"
SESSION_COOKIE_KEY = "session_cookie"

HOME_PAGE = "home"
LOGIN_PAGE = "login"
REGISTER_PAGE = "register"
VERIFY_PAGE = "verify"
FORGOT_PAGE = "forgot"
RESET_PAGE = "reset"
SIMULATOR_PAGE = "simulator"

VALID_PAGES = (
    HOME_PAGE,
    LOGIN_PAGE,
    REGISTER_PAGE,
    VERIFY_PAGE,
    FORGOT_PAGE,
    RESET_PAGE,
    SIMULATOR_PAGE,
)


def init_session_state() -> None:
    """Initialize required session state keys with safe defaults."""
    if PAGE_KEY not in st.session_state or st.session_state[PAGE_KEY] not in VALID_PAGES:
        st.session_state[PAGE_KEY] = HOME_PAGE
    if MODE_KEY not in st.session_state:
        st.session_state[MODE_KEY] = "DEMO"
    if DEMO_SEED_KEY not in st.session_state:
        st.session_state[DEMO_SEED_KEY] = 42
    if USER_KEY not in st.session_state:
        st.session_state[USER_KEY] = None
    if PENDING_EMAIL_KEY not in st.session_state:
        st.session_state[PENDING_EMAIL_KEY] = ""
    if SESSION_COOKIE_KEY not in st.session_state:
        st.session_state[SESSION_COOKIE_KEY] = None


def navigate_to(page: str) -> None:
    """Navigate to a named page state."""
    st.session_state[PAGE_KEY] = page if page in VALID_PAGES else HOME_PAGE


def start_demo_mode(seed: int = 42) -> None:
    """Activate demo mode with a deterministic seed and navigate to the simulator."""
    st.session_state[MODE_KEY] = "DEMO"
    st.session_state[DEMO_SEED_KEY] = seed
    st.session_state[PAGE_KEY] = SIMULATOR_PAGE


def get_db_path() -> str | None:
    """Return configured database path override from session state if set."""
    val = st.session_state.get(DB_PATH_KEY)
    return str(val) if val else None


def set_authenticated_user(user: dict[str, Any], session_cookie: str | None = None) -> None:
    """Store authenticated user summary and session cookie in session state."""
    st.session_state[USER_KEY] = user
    st.session_state[SESSION_COOKIE_KEY] = session_cookie


def clear_authenticated_user() -> None:
    """Clear authenticated user summary and session cookie from session state."""
    st.session_state[USER_KEY] = None
    st.session_state[SESSION_COOKIE_KEY] = None
