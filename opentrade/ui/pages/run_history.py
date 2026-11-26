"""Run History page listing saved simulation runs with one-click deterministic re-run (T20.1)."""

import streamlit as st

from opentrade.services.errors import AppError
from opentrade.services.runs import list_runs_db_path, rerun_by_id_db_path
from opentrade.ui.components.badge import render_provenance_badge
from opentrade.ui.state import HOME_PAGE, USER_KEY, get_db_path, navigate_to


def render_run_history_page() -> None:
    """Render saved simulation runs for the signed-in user with deterministic re-run."""
    st.title("Run History")
    st.caption(
        "Inspect saved impact runs and verify deterministic reproducibility. "
        "Prototype. Not investment advice."
    )

    if st.button("Back to Home", key="history_back_home"):
        navigate_to(HOME_PAGE)
        return

    user = st.session_state.get(USER_KEY)
    if not isinstance(user, dict) or "id" not in user:
        st.info("Sign in with a verified account to view and re-run saved runs.")
        return

    user_id = int(user["id"])
    db_path = get_db_path()
    runs = list_runs_db_path(db_path, user_id=user_id, limit=50)
    if not runs:
        st.info("No saved runs yet. Save a run from the Impact Lab.")
        return

    for run in runs:
        render_provenance_badge(str(run.get("provenance", "SYNTHETIC")))
        st.markdown(
            f"**{run['name']}** | Seed: `{run['seed']}` | "
            f"Fingerprint: `{str(run['fingerprint'])[:12]}...`"
        )
        if st.button(f"Re-run {run['name']}", key=f"rerun_btn_{run['id']}"):
            try:
                rerun = rerun_by_id_db_path(db_path, str(run["id"]), user_id)
                st.success(f"Deterministic re-run complete. Fingerprint: {rerun['fingerprint']}")
            except AppError as exc:
                st.error(exc.message)
