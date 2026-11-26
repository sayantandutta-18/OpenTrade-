"""Tests for calibrated liquidity profiles, offline calibration, and factor radar (T6.1-T6.2).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-27), docs/SRS.md (FR-37, FR-38, FR-52),
and docs/CODING_STANDARDS.md (§8).
"""

from pathlib import Path

import pytest

from opentrade.config import Provenance
from opentrade.services.errors import ValidationError
from opentrade.services.profiles import (
    RADAR_FACTORS,
    calibrate_profile_from_bars,
    load_calibrated_profiles,
    score_factor_radar,
    validate_profile_schema,
)


def test_calibrated_profiles_json_schema_loads_cleanly_t6_1() -> None:
    """T6.1, FR-37, FR-52: Bundled calibrated_profiles.json validates schema with CALIBRATED."""
    profiles = load_calibrated_profiles()
    assert len(profiles) >= 5
    for sym, prof in profiles.items():
        assert prof.symbol == sym
        assert prof.provenance is Provenance.CALIBRATED
        assert prof.tick_size > 0
        assert prof.typical_spread_bps > 0
        assert prof.top_depth_shares > 0
        assert prof.daily_volatility >= 0


def test_validate_profile_schema_rejects_invalid_or_real_provenance_t6_1() -> None:
    """T6.1, CODING_STANDARDS §8: Schema validator rejects REAL provenance or invalid fields."""
    bad_real = {
        "symbol": "AAPL",
        "tick_size": 0.01,
        "typical_spread_bps": 1.2,
        "top_depth_shares": 1000,
        "arrival_rate_per_sec": 5.0,
        "daily_volatility": 0.015,
        "source": "yfinance_ohlcv",
        "calibrated_at": "2026-01-15T00:00:00Z",
        "provenance": "REAL",
    }
    with pytest.raises(ValidationError):
        validate_profile_schema(bad_real)

    bad_neg = {**bad_real, "provenance": "CALIBRATED", "typical_spread_bps": -1.0}
    with pytest.raises(ValidationError):
        validate_profile_schema(bad_neg)


def test_offline_calibration_from_bars_fixture_t6_1() -> None:
    """T6.1, FR-37: Offline calibration computes spread, depth, volatility from OHLCV fixture."""
    bars = [
        {"close": 100.0, "high": 101.0, "low": 99.0, "volume": 1_000_000.0},
        {"close": 102.0, "high": 103.0, "low": 101.0, "volume": 1_200_000.0},
        {"close": 101.0, "high": 102.5, "low": 100.0, "volume": 900_000.0},
        {"close": 103.0, "high": 104.0, "low": 102.0, "volume": 1_100_000.0},
    ]
    prof = calibrate_profile_from_bars("TEST", bars)
    assert prof.symbol == "TEST"
    assert prof.provenance is Provenance.CALIBRATED
    assert prof.typical_spread_bps > 0
    assert prof.top_depth_shares > 0
    assert prof.daily_volatility > 0


def test_factor_radar_scoring_preserves_missing_as_none_ac27_t6_2(tmp_path: Path) -> None:
    """T6.2, AC-27, FR-38: Missing traits stay None (never 0 or average) and weights renormalize."""
    radars = score_factor_radar(["AAPL", "JPM", "TSLA"])
    assert len(radars) == 3

    by_sym = {r.symbol: r for r in radars}
    # TSLA in bundled calibrated_profiles.json intentionally has missing 'value' trait (null)
    tsla = by_sym["TSLA"]
    assert tsla.provenance is Provenance.CALIBRATED
    assert set(tsla.scores.keys()) == set(RADAR_FACTORS)
    assert tsla.scores["value"] is None
    assert "value" in tsla.missing_factors
    assert tsla.composite_score is not None
    assert 0.0 <= tsla.composite_score <= 100.0

    # Unknown symbol with no calibrated profile returns all None scores (never fabricated)
    unknown = score_factor_radar(["NONEXISTENT"])[0]
    assert all(v is None for v in unknown.scores.values())
    assert unknown.composite_score is None
    assert len(unknown.missing_factors) == len(RADAR_FACTORS)
