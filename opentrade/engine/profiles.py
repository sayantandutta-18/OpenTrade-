"""Preset liquidity profiles with provenance labels (T1.10)."""

from dataclasses import dataclass
from enum import StrEnum


class EngineProvenance(StrEnum):
    """Engine-local provenance labels (never REAL for simulated outputs)."""

    SYNTHETIC = "SYNTHETIC"
    CALIBRATED = "CALIBRATED"


@dataclass(frozen=True)
class LiquidityProfile:
    """Immutable liquidity and order-flow regime parameters."""

    profile_id: str
    provenance: EngineProvenance
    tick_size: float = 0.01
    base_mid_ticks: int = 10_000
    initial_levels: int = 20
    level_qty: int = 500
    limit_rate: float = 0.60
    market_rate: float = 0.20
    cancel_rate: float = 0.20
    power_law_alpha: float = 1.5
    hawkes_excitation: float = 0.0
    volatility_ticks: int = 2


PRESET_PROFILES: dict[str, LiquidityProfile] = {
    "synthetic_default": LiquidityProfile(
        profile_id="synthetic_default",
        provenance=EngineProvenance.SYNTHETIC,
        tick_size=0.01,
        base_mid_ticks=10_000,
        initial_levels=25,
        level_qty=600,
        limit_rate=0.60,
        market_rate=0.20,
        cancel_rate=0.20,
        power_law_alpha=1.5,
        hawkes_excitation=0.0,
        volatility_ticks=2,
    ),
    "thin_book": LiquidityProfile(
        profile_id="thin_book",
        provenance=EngineProvenance.SYNTHETIC,
        tick_size=0.01,
        base_mid_ticks=10_000,
        initial_levels=12,
        level_qty=120,
        limit_rate=0.50,
        market_rate=0.25,
        cancel_rate=0.25,
        power_law_alpha=1.2,
        hawkes_excitation=0.1,
        volatility_ticks=4,
    ),
    "deep_book": LiquidityProfile(
        profile_id="deep_book",
        provenance=EngineProvenance.CALIBRATED,
        tick_size=0.01,
        base_mid_ticks=10_000,
        initial_levels=40,
        level_qty=2_000,
        limit_rate=0.65,
        market_rate=0.18,
        cancel_rate=0.17,
        power_law_alpha=1.8,
        hawkes_excitation=0.05,
        volatility_ticks=1,
    ),
    "high_volatility": LiquidityProfile(
        profile_id="high_volatility",
        provenance=EngineProvenance.SYNTHETIC,
        tick_size=0.01,
        base_mid_ticks=10_000,
        initial_levels=20,
        level_qty=300,
        limit_rate=0.45,
        market_rate=0.35,
        cancel_rate=0.20,
        power_law_alpha=1.1,
        hawkes_excitation=0.35,
        volatility_ticks=6,
    ),
}


def get_profile(profile_id: str) -> LiquidityProfile:
    """Return a preset LiquidityProfile by ID, or raise ValueError if unknown."""
    profile = PRESET_PROFILES.get(profile_id)
    if profile is None:
        raise ValueError(f"Unknown liquidity profile: {profile_id!r}")
    return profile
