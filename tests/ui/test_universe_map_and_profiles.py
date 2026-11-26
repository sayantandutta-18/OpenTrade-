"""Headless Streamlit UI tests for Universe Map (T5.1) and Profiles/Factor Radar (T6.2).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-23 to AC-27, AC-41, AC-42) and docs/USER_FLOW.md (Flow 5).
"""

from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "opentrade" / "ui" / "app.py")


def _all_text(at: AppTest) -> str:
    """Collect visible text across standard Streamlit elements."""
    chunks: list[str] = []
    for attr in (
        "markdown",
        "caption",
        "info",
        "warning",
        "error",
        "success",
        "title",
        "header",
        "subheader",
        "text",
    ):
        for el in getattr(at, attr, []):
            val = getattr(el, "value", "")
            if val:
                chunks.append(str(val))
    for metric in getattr(at, "metric", []):
        chunks.append(f"{metric.label}: {metric.value}")
    return "\n".join(chunks)


def _find_button(at: AppTest, label: str) -> Any:
    """Find a button by exact label in the rendered AppTest tree."""
    for btn in at.button:
        if btn.label == label:
            return btn
    raise AssertionError(f"Button {label!r} not found; available: {[b.label for b in at.button]}")


def test_universe_map_search_preset_and_six_company_limit_t5_1() -> None:
    """T5.1, AC-23, AC-24, AC-25, AC-26, AC-42: Map, search, presets, and 6-company cap."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["current_page"] = "universe_map"
    at.run()
    assert not at.exception

    rendered = _all_text(at)
    assert "Prototype. Not investment advice." in rendered
    assert "0 of 6 selected" in rendered
    assert "REAL" in rendered

    # Load Global Banks preset (6 companies)
    _find_button(at, "Load preset").click().run()
    assert not at.exception
    assert "6 of 6 selected" in _all_text(at)

    # Attempting to add a 7th company (AAPL) triggers COMPARE_LIMIT notice and stays at 6
    at.text_input[0].input("AAPL")
    _find_button(at, "Add symbol").click().run()
    assert not at.exception
    after_limit = _all_text(at)
    assert "You can compare up to six companies" in after_limit
    assert "6 of 6 selected" in after_limit


def test_profiles_factor_radar_shows_missing_not_zero_ac27_t6_2() -> None:
    """T6.2, AC-27, AC-42, FR-52: Factor radar displays 'missing' for None traits and CALIBRATED."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["current_page"] = "profiles"
    at.session_state["compare_symbols"] = ["AAPL", "TSLA"]
    at.run()
    assert not at.exception

    rendered = _all_text(at)
    assert "Prototype. Not investment advice." in rendered
    assert "CALIBRATED" in rendered
    assert "missing" in rendered.lower()
