"""Tests for correlation analytics (T14.1) and calm-vs-news slippage (T9.2).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-32, AC-33) and docs/SRS.md (FR-41 to FR-43, FR-52).
"""

import pytest

from opentrade.services.correlation import (
    analyze_correlation,
    concentration_vs_count_curve,
    diversification_verdict,
    effective_holdings,
)
from opentrade.services.news import compare_calm_vs_news_slippage


def test_diversification_verdict_boundaries_ac32_t14_1() -> None:
    """T14.1, AC-32: Verdict thresholds at 0.3 and 0.6 return exact required strings."""
    assert diversification_verdict(0.0) == "well diversified"
    assert diversification_verdict(0.299) == "well diversified"
    assert diversification_verdict(0.3) == "moderate"
    assert diversification_verdict(0.45) == "moderate"
    assert diversification_verdict(0.6) == "moderate"
    assert diversification_verdict(0.601) == "concentrated"
    assert diversification_verdict(0.95) == "concentrated"


def test_effective_holdings_inverse_herfindahl_ac33_t14_1() -> None:
    """T14.1, AC-33, FR-43: Effective holdings equals 1 / sum(w_i^2) within 0.01."""
    assert abs(effective_holdings([0.25, 0.25, 0.25, 0.25]) - 4.0) < 0.01
    expected_conc = 1.0 / (0.7**2 + 0.1**2 + 0.1**2 + 0.1**2)
    assert abs(effective_holdings([0.7, 0.1, 0.1, 0.1]) - expected_conc) < 0.01

    with pytest.raises(ValueError):
        effective_holdings([])


def test_analyze_correlation_and_concentration_curve_t14_1() -> None:
    """T14.1, AC-32, AC-33, FR-52: Returns matrix, verdict, effective N, and provenance."""
    res = analyze_correlation(["AAPL", "MSFT", "JPM", "XOM"])
    assert len(res["matrix"]) == 4
    assert res["nominal_holdings"] == 4
    assert 1.0 <= res["effective_holdings"] <= 4.0
    assert res["verdict"] in ("well diversified", "moderate", "concentrated")
    assert res["label"] in ("REAL", "SIMULATED")

    curve = concentration_vs_count_curve(max_n=10, avg_corr=0.25)
    assert len(curve) == 10
    assert curve[0]["nominal_n"] == 1
    assert curve[-1]["effective_n"] > curve[0]["effective_n"]


def test_compare_calm_vs_news_slippage_with_ci_t9_2() -> None:
    """T9.2, FR-52: News-shock regime yields higher slippage than calm regime with 95% CI."""
    comp = compare_calm_vs_news_slippage(
        profile_id="synthetic_default",
        seed=42,
        qty=600,
        trials=8,
    )
    assert comp["provenance"] == "SYNTHETIC"
    assert comp["calm"]["ci95"][0] <= comp["calm"]["mean_bps"] <= comp["calm"]["ci95"][1]
    assert comp["news"]["ci95"][0] <= comp["news"]["mean_bps"] <= comp["news"]["ci95"][1]
    assert comp["news"]["mean_bps"] > comp["calm"]["mean_bps"]
