"""Impact sweep, log-log power-law fit with 95% CI, and decay curves (T3.2-T3.3)."""

import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any

from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.impact import inject_market_order
from opentrade.engine.matching import submit_order
from opentrade.engine.order_flow import generate_order_flow, seed_initial_book
from opentrade.engine.profiles import EngineProvenance, LiquidityProfile, get_profile

DEFAULT_SWEEP_SIZES: tuple[int, ...] = (100, 300, 1000, 3000, 6000, 10_000)

# Two-tailed 95% t-distribution critical values by degrees of freedom (df = n - 2)
_T_CRIT_95: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
}


@dataclass(frozen=True)
class SweepPoint:
    """Single order-size point in a market impact sweep."""

    size: int
    filled_qty: int
    slippage_ticks: float
    slippage_bps: float
    arrival_mid_ticks: float
    avg_fill_price_ticks: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize sweep point to JSON-compatible dictionary."""
        return {
            "size": self.size,
            "filled_qty": self.filled_qty,
            "slippage_ticks": self.slippage_ticks,
            "slippage_bps": self.slippage_bps,
            "arrival_mid_ticks": self.arrival_mid_ticks,
            "avg_fill_price_ticks": self.avg_fill_price_ticks,
        }


@dataclass(frozen=True)
class PowerLawFit:
    """Log-log OLS power-law fit: log(impact) = alpha + beta * log(size)."""

    alpha: float
    beta: float
    r_squared: float
    ci95_low: float
    ci95_high: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize fit parameters and 95% confidence interval."""
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "r_squared": self.r_squared,
            "ci95": [self.ci95_low, self.ci95_high],
        }


@dataclass(frozen=True)
class ImpactSweepResult:
    """Complete result of an impact sweep across multiple order sizes (AC-18 to AC-20)."""

    profile_id: str
    seed: int
    side: Side
    provenance: EngineProvenance
    points: tuple[SweepPoint, ...]
    fit: PowerLawFit
    book_capped: bool
    max_available_depth: int
    event_log_sha256: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize sweep result to JSON-compatible dictionary."""
        return {
            "profile_id": self.profile_id,
            "seed": self.seed,
            "side": self.side.value,
            "provenance": self.provenance.value,
            "points": [pt.to_dict() for pt in self.points],
            "fit": self.fit.to_dict(),
            "book_capped": self.book_capped,
            "max_available_depth": self.max_available_depth,
            "event_log_sha256": self.event_log_sha256,
        }


@dataclass(frozen=True)
class DecayPoint:
    """Single time-step sample on an impact relaxation curve."""

    step: int
    mid_ticks: float
    impact_bps: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize decay point."""
        return {"step": self.step, "mid_ticks": self.mid_ticks, "impact_bps": self.impact_bps}


@dataclass(frozen=True)
class ImpactDecayResult:
    """Impact decay curve separating temporary and permanent impact (T3.3)."""

    arrival_mid_ticks: float
    peak_impact_bps: float
    permanent_impact_bps: float
    temporary_impact_bps: float
    curve: tuple[DecayPoint, ...]
    provenance: EngineProvenance

    def to_dict(self) -> dict[str, Any]:
        """Serialize decay result."""
        return {
            "arrival_mid_ticks": self.arrival_mid_ticks,
            "peak_impact_bps": self.peak_impact_bps,
            "permanent_impact_bps": self.permanent_impact_bps,
            "temporary_impact_bps": self.temporary_impact_bps,
            "curve": [pt.to_dict() for pt in self.curve],
            "provenance": self.provenance.value,
        }


def _t_critical_95(df: int) -> float:
    """Return two-tailed 95% t-critical value for degrees of freedom df."""
    if df <= 0:
        return 1.96
    if df in _T_CRIT_95:
        return _T_CRIT_95[df]
    if df < 15:
        return 2.179
    if df < 30:
        return 2.045
    return 1.96


def fit_power_law_log_log(
    sizes: list[int] | tuple[int, ...],
    impacts_bps: list[float] | tuple[float, ...],
) -> PowerLawFit:
    """Fit log(impact_bps) = alpha + beta * log(size) via OLS with 95% CI (AC-19)."""
    xs: list[float] = []
    ys: list[float] = []
    for s, imp in zip(sizes, impacts_bps, strict=True):
        if s > 0 and imp > 0.0:
            xs.append(math.log(s))
            ys.append(math.log(imp))

    n = len(xs)
    if n < 2:
        raise ValueError("Need at least two positive (size, impact) points for log-log fit")

    x_bar = sum(xs) / n
    y_bar = sum(ys) / n
    ss_xx = sum((x - x_bar) ** 2 for x in xs)
    if ss_xx <= 0.0:
        raise ValueError("Sizes must contain at least two distinct values")

    ss_xy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys, strict=True))
    beta = ss_xy / ss_xx
    alpha = y_bar - beta * x_bar

    ss_res = sum((y - (alpha + beta * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    ss_tot = sum((y - y_bar) ** 2 for y in ys)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0.0 else 1.0

    df = n - 2
    se_beta = math.sqrt((ss_res / df) / ss_xx) if df > 0 else 0.0
    margin = _t_critical_95(df) * se_beta
    return PowerLawFit(
        alpha=alpha,
        beta=beta,
        r_squared=r_squared,
        ci95_low=beta - margin,
        ci95_high=beta + margin,
    )


def _seed_concave_sweep_book(
    book: OrderBook,
    profile: LiquidityProfile,
    rng: random.Random,
) -> None:
    """Seed a concave book where level depth grows with distance from touch."""
    mid = profile.base_mid_ticks
    for offset in range(1, profile.initial_levels + 1):
        # Depth scaling ~ offset^0.9 yields concave ~square-root impact (beta ~ 0.5)
        scale = offset**0.9
        bid_qty = max(10, int(profile.level_qty * 0.4 * scale * (0.9 + 0.2 * rng.random())))
        ask_qty = max(10, int(profile.level_qty * 0.4 * scale * (0.9 + 0.2 * rng.random())))
        submit_order(book, Side.BUY, OrderType.LIMIT, qty=bid_qty, price_ticks=mid - offset)
        submit_order(book, Side.SELL, OrderType.LIMIT, qty=ask_qty, price_ticks=mid + offset)


def run_impact_sweep(
    profile_id: str = "synthetic_default",
    seed: int = 42,
    sizes: tuple[int, ...] = DEFAULT_SWEEP_SIZES,
    side: Side = Side.BUY,
) -> ImpactSweepResult:
    """Execute a multi-size impact sweep and log-log power-law fit (AC-18 to AC-20)."""
    profile = get_profile(profile_id)
    probe_book = OrderBook()
    _seed_concave_sweep_book(probe_book, profile, random.Random(seed))  # noqa: S311
    opp_side = Side.SELL if side is Side.BUY else Side.BUY
    max_depth = probe_book.total_resting_qty(opp_side)
    book_capped = max_depth < max(sizes)

    points: list[SweepPoint] = []
    hashes: list[str] = []
    for raw_size in sizes:
        target_size = min(raw_size, max_depth) if max_depth > 0 else raw_size
        if target_size <= 0:
            continue
        book = OrderBook()
        _seed_concave_sweep_book(book, profile, random.Random(seed))  # noqa: S311
        inj = inject_market_order(book, side=side, qty=target_size, provenance=profile.provenance)
        points.append(
            SweepPoint(
                size=target_size,
                filled_qty=inj.filled_qty,
                slippage_ticks=inj.slippage_ticks,
                slippage_bps=inj.slippage_bps,
                arrival_mid_ticks=inj.arrival_mid_ticks,
                avg_fill_price_ticks=inj.avg_fill_price_ticks,
            )
        )
        hashes.append(book.event_log_sha256())

    fit = fit_power_law_log_log([p.size for p in points], [p.slippage_bps for p in points])
    agg_sha = hashlib.sha256(json.dumps(hashes, separators=(",", ":")).encode("utf-8")).hexdigest()
    return ImpactSweepResult(
        profile_id=profile.profile_id,
        seed=seed,
        side=side,
        provenance=profile.provenance,
        points=tuple(points),
        fit=fit,
        book_capped=book_capped,
        max_available_depth=max_depth,
        event_log_sha256=agg_sha,
    )


def measure_impact_decay(
    profile_id: str = "synthetic_default",
    seed: int = 42,
    qty: int = 2000,
    side: Side = Side.BUY,
    relaxation_steps: int = 40,
    sample_every: int = 5,
) -> ImpactDecayResult:
    """Measure peak, temporary, and permanent impact across post-trade flow (T3.3)."""
    profile = get_profile(profile_id)
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(seed))  # noqa: S311
    inj = inject_market_order(book, side=side, qty=qty, provenance=profile.provenance)

    sign = 1.0 if side is Side.BUY else -1.0
    arrival = inj.arrival_mid_ticks
    curve: list[DecayPoint] = [
        DecayPoint(step=0, mid_ticks=inj.post_mid_ticks, impact_bps=inj.slippage_bps)
    ]

    elapsed = 0
    while elapsed < relaxation_steps:
        chunk = min(sample_every, relaxation_steps - elapsed)
        generate_order_flow(book, profile, seed=seed + elapsed + 1, steps=chunk)
        elapsed += chunk
        mid_now = book.mid_price_ticks() or arrival
        imp_now = sign * ((mid_now - arrival) / arrival) * 10_000.0
        curve.append(DecayPoint(step=elapsed, mid_ticks=mid_now, impact_bps=imp_now))

    perm_bps = curve[-1].impact_bps
    temp_bps = inj.slippage_bps - perm_bps
    return ImpactDecayResult(
        arrival_mid_ticks=arrival,
        peak_impact_bps=inj.slippage_bps,
        permanent_impact_bps=perm_bps,
        temporary_impact_bps=temp_bps,
        curve=tuple(curve),
        provenance=profile.provenance,
    )
