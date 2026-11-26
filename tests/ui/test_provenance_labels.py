"""Release verification T-X.1: Provenance labels and prototype banner across all routes (AC-42)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from opentrade.storage.migrate import run_migrations
from opentrade.ui.state import DB_PATH_KEY, PAGE_KEY, VALID_PAGES

APP_PATH = str(Path(__file__).resolve().parents[2] / "opentrade" / "ui" / "app.py")


def _all_text(at: AppTest) -> str:
    parts = (
        [e.value for e in at.markdown]
        + [e.value for e in at.caption]
        + [e.value for e in at.title]
        + [e.value for e in at.header]
        + [e.value for e in at.subheader]
        + [e.value for e in at.info]
        + [e.value for e in at.warning]
        + [e.value for e in at.error]
        + [e.value for e in at.success]
    )
    return "\n".join(str(p) for p in parts if p is not None)


def test_prototype_banner_and_no_exceptions_across_all_pages_ac42(tmp_path: Path) -> None:
    """T-X.1, AC-42, FR-53: Every route in VALID_PAGES renders cleanly and shows banner."""
    db_path = str(tmp_path / "all_routes.sqlite3")
    run_migrations(db_path)

    for page in VALID_PAGES:
        at = AppTest.from_file(APP_PATH, default_timeout=15)
        at.session_state[DB_PATH_KEY] = db_path
        at.session_state[PAGE_KEY] = page
        at.run()
        assert not at.exception, f"Page {page!r} raised exception: {at.exception}"
        text = _all_text(at)
        assert "Prototype. Not investment advice." in text, f"Banner missing on page {page!r}"


def test_simulation_and_analytics_screens_show_provenance_badges_tx1(tmp_path: Path) -> None:
    """T-X.1: Data/simulation screens display explicit provenance labels."""
    db_path = str(tmp_path / "prov_routes.sqlite3")
    run_migrations(db_path)

    data_pages = ("simulator", "impact_lab", "profiles", "analyst", "tour", "summary", "validation")
    allowed = ("REAL", "CALIBRATED", "SYNTHETIC", "DEMO", "LIVE")
    for page in data_pages:
        at = AppTest.from_file(APP_PATH, default_timeout=15)
        at.session_state[DB_PATH_KEY] = db_path
        at.session_state[PAGE_KEY] = page
        at.run()
        assert not at.exception
        text = _all_text(at)
        assert any(lbl in text for lbl in allowed), f"No provenance label on {page!r}"
