"""Headless Streamlit UI tests for News Lab calm-vs-news (T9.2) and Correlation screens (T14.2).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-32, AC-33, AC-41, AC-42) and docs/USER_FLOW.md (Flow 8).
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


def test_news_lab_calm_vs_news_slippage_comparison_t9_2() -> None:
    """T9.2, AC-41, AC-42, FR-52: News Lab compares calm vs news slippage with 95% CI."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["current_page"] = "news_lab"
    at.run()
    assert not at.exception

    _find_button(at, "Compare calm vs news").click().run()
    assert not at.exception
    rendered = _all_text(at)
    assert "Prototype. Not investment advice." in rendered
    assert "SYNTHETIC" in rendered
    assert "Calm slippage" in rendered
    assert "News shock slippage" in rendered
    assert "95% CI" in rendered


def test_correlation_overview_and_concentration_vs_count_t14_2() -> None:
    """T14.2, AC-32, AC-33, AC-42: Correlation screen shows matrix, verdict, and effective N."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.session_state["current_page"] = "correlation"
    at.session_state["compare_symbols"] = ["AAPL", "MSFT", "JPM", "XOM"]
    at.run()
    assert not at.exception

    rendered = _all_text(at)
    assert "Prototype. Not investment advice." in rendered
    assert "SIMULATED" in rendered
    assert "Effective holdings" in rendered
    assert "Nominal holdings" in rendered
    assert any(v in rendered for v in ("well diversified", "moderate", "concentrated"))
