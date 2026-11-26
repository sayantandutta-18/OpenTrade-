"""Calibrated liquidity profiles schema, offline calibration, and factor radar (T6.1-T6.2)."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opentrade.config import Provenance, parse_provenance
from opentrade.services.errors import ValidationError

CALIBRATED_PROFILES_PATH = Path("data/calibrated_profiles.json")
RADAR_FACTORS: tuple[str, ...] = (
    "liquidity",
    "volatility",
    "size",
    "growth",
    "value",
    "momentum",
)


@dataclass(frozen=True)
class CalibratedProfile:
    """Validated company-level liquidity profile with CALIBRATED provenance."""

    symbol: str
    tick_size: float
    typical_spread_bps: float
    top_depth_shares: int
    arrival_rate_per_sec: float
    daily_volatility: float
    source: str
    calibrated_at: str
    provenance: Provenance
    raw_metrics: dict[str, float | None]


@dataclass(frozen=True)
class CompanyRadar:
    """Normalized factor radar scores preserving missing traits as None (AC-27)."""

    symbol: str
    scores: dict[str, float | None]
    composite_score: float | None
    available_factors: int
    missing_factors: tuple[str, ...]
    provenance: Provenance


def validate_profile_schema(data: dict[str, Any]) -> CalibratedProfile:
    """Validate a calibrated profile dictionary against schema and provenance rules (T6.1)."""
    symbol = str(data.get("symbol") or "").strip().upper()
    source = str(data.get("source") or "").strip()
    calibrated_at = str(data.get("calibrated_at") or "").strip()
    if not symbol or not source or not calibrated_at:
        raise ValidationError("Calibrated profile requires symbol, source, and calibrated_at")

    prov = parse_provenance(str(data.get("provenance") or ""))
    if prov is not Provenance.CALIBRATED:
        raise ValidationError(
            f"Calibrated profile must carry CALIBRATED provenance, got {prov.value}"
        )

    try:
        tick_size = float(data["tick_size"])
        spread_bps = float(data["typical_spread_bps"])
        top_depth = int(data["top_depth_shares"])
        arrival_rate = float(data["arrival_rate_per_sec"])
        daily_vol = float(data["daily_volatility"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Calibrated profile missing or malformed numeric fields") from exc

    if tick_size <= 0 or spread_bps <= 0 or top_depth <= 0 or arrival_rate <= 0 or daily_vol < 0:
        raise ValidationError("Calibrated profile numeric parameters must be positive")

    raw_in = data.get("raw_metrics") or {}
    if not isinstance(raw_in, dict):
        raise ValidationError("raw_metrics must be a JSON object")

    raw_metrics: dict[str, float | None] = {}
    for factor in RADAR_FACTORS:
        val = raw_in.get(factor)
        if val is None:
            raw_metrics[factor] = None
        else:
            fval = float(val)
            raw_metrics[factor] = max(0.0, min(100.0, fval))

    return CalibratedProfile(
        symbol=symbol,
        tick_size=tick_size,
        typical_spread_bps=spread_bps,
        top_depth_shares=top_depth,
        arrival_rate_per_sec=arrival_rate,
        daily_volatility=daily_vol,
        source=source,
        calibrated_at=calibrated_at,
        provenance=prov,
        raw_metrics=raw_metrics,
    )


def load_calibrated_profiles(
    path: str | Path = CALIBRATED_PROFILES_PATH,
) -> dict[str, CalibratedProfile]:
    """Load and validate all calibrated liquidity profiles from JSON."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    profiles: dict[str, CalibratedProfile] = {}
    for item in raw.get("profiles", []):
        prof = validate_profile_schema(item)
        profiles[prof.symbol] = prof
    return profiles


def calibrate_profile_from_bars(
    symbol: str,
    bars: list[dict[str, float]],
    source: str = "yfinance_ohlcv",
    calibrated_at: str = "2026-01-15T00:00:00Z",
) -> CalibratedProfile:
    """Calibrate a liquidity profile offline from OHLCV bar dicts (T6.1)."""
    if len(bars) < 2:
        raise ValidationError("Need at least 2 OHLCV bars to calibrate volatility")

    closes = [float(b["close"]) for b in bars]
    returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i] > 0 and closes[i - 1] > 0
    ]
    mean_ret = sum(returns) / len(returns)
    var = sum((r - mean_ret) ** 2 for r in returns) / max(1, len(returns) - 1)
    daily_vol = math.sqrt(var)

    hl_ratios = [
        max(0.0001, (float(b["high"]) - float(b["low"])) / float(b["close"]))
        for b in bars
        if float(b["close"]) > 0
    ]
    # Corwin-Schultz-style spread proxy scaled into realistic bps
    spread_bps = max(0.5, (sum(hl_ratios) / len(hl_ratios)) * 100.0)
    avg_vol = sum(float(b["volume"]) for b in bars) / len(bars)
    top_depth = max(100, int(avg_vol * 0.001))
    arrival_rate = max(1.0, avg_vol / 100_000.0)

    return CalibratedProfile(
        symbol=symbol.strip().upper(),
        tick_size=0.01,
        typical_spread_bps=round(spread_bps, 2),
        top_depth_shares=top_depth,
        arrival_rate_per_sec=round(arrival_rate, 2),
        daily_volatility=round(daily_vol, 5),
        source=source,
        calibrated_at=calibrated_at,
        provenance=Provenance.CALIBRATED,
        raw_metrics={
            "liquidity": min(100.0, round(top_depth / 25.0, 1)),
            "volatility": min(100.0, round(daily_vol * 2000.0, 1)),
            "size": None,
            "growth": None,
            "value": None,
            "momentum": min(100.0, round(50.0 + mean_ret * 1000.0, 1)),
        },
    )


def score_factor_radar(
    symbols: list[str],
    profiles_path: str | Path = CALIBRATED_PROFILES_PATH,
) -> list[CompanyRadar]:
    """Score factor radar across symbols, preserving missing values as None (AC-27, T6.2)."""
    profiles = load_calibrated_profiles(profiles_path)
    radars: list[CompanyRadar] = []

    for sym in symbols:
        clean = sym.strip().upper()
        prof = profiles.get(clean)
        if prof is None:
            radars.append(
                CompanyRadar(
                    symbol=clean,
                    scores={f: None for f in RADAR_FACTORS},
                    composite_score=None,
                    available_factors=0,
                    missing_factors=RADAR_FACTORS,
                    provenance=Provenance.CALIBRATED,
                )
            )
            continue

        scores: dict[str, float | None] = {}
        missing: list[str] = []
        present_vals: list[float] = []
        for factor in RADAR_FACTORS:
            val = prof.raw_metrics.get(factor)
            if val is None:
                scores[factor] = None
                missing.append(factor)
            else:
                scores[factor] = val
                present_vals.append(val)

        composite = round(sum(present_vals) / len(present_vals), 2) if present_vals else None
        radars.append(
            CompanyRadar(
                symbol=clean,
                scores=scores,
                composite_score=composite,
                available_factors=len(present_vals),
                missing_factors=tuple(missing),
                provenance=prof.provenance,
            )
        )
    return radars
