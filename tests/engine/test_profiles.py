"""Tests for preset liquidity profiles (T1.10).

Follows docs/SRS.md (FR-37, FR-52) and docs/CODING_STANDARDS.md (§8).
"""

import pytest

from opentrade.engine.profiles import (
    PRESET_PROFILES,
    EngineProvenance,
    get_profile,
)


def test_preset_profiles_exist_and_have_valid_provenance() -> None:
    """FR-37, FR-52: All four preset profiles exist and never carry REAL provenance."""
    expected = ("synthetic_default", "thin_book", "deep_book", "high_volatility")
    for name in expected:
        assert name in PRESET_PROFILES
        prof = get_profile(name)
        assert prof.profile_id == name
        assert prof.provenance in (EngineProvenance.SYNTHETIC, EngineProvenance.CALIBRATED)
        assert prof.provenance.value != "REAL"
        assert prof.base_mid_ticks > 0
        assert prof.initial_levels > 0
        assert prof.level_qty > 0


def test_unknown_profile_raises_value_error() -> None:
    """FR-37: Unknown profile ID raises ValueError."""
    with pytest.raises(ValueError):
        get_profile("non_existent_profile")
