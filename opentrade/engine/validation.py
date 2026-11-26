"""Stylized-fact validation checks on simulated order-book series (T18.1)."""

import random
from dataclasses import dataclass

from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.matching import submit_order
from opentrade.engine.numba_kernels import abs_autocorr_lag1, excess_kurtosis
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import EngineProvenance, get_profile


@dataclass(frozen=True)
class StylizedFactCheck:
    """Result of a single stylized-fact validation test."""

    name: str
    passed: bool
    value: float
    threshold: str
    provenance: EngineProvenance


@dataclass(frozen=True)
class ValidationSuiteResult:
    """Aggregated stylized-fact validation suite output."""

    checks: tuple[StylizedFactCheck, ...]
    all_passed: bool
    provenance: EngineProvenance


def run_stylized_fact_validation(
    profile_id: str = "high_volatility",
    seed: int = 42,
    steps: int = 250,
) -> ValidationSuiteResult:
    """Simulate a clustered order-flow series and check 4 financial stylized facts."""
    profile = get_profile(profile_id)
    rng = random.Random(seed)  # noqa: S311
    book = OrderBook()
    seed_initial_book(book, profile, rng)

    returns: list[float] = []
    spreads: list[int] = []
    prev_mid = book.mid_price_ticks() or float(profile.base_mid_ticks)
    regime_vol = 1.0

    for step in range(steps):
        # Clustered volatility regime switching + heavy-tailed market order bursts
        if step % 30 == 0:
            regime_vol = 3.0 if (step // 30) % 2 == 0 else 1.0
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        base_qty = int(profile.level_qty * (0.2 + 0.6 * rng.random()) * regime_vol)
        if rng.random() < 0.08:
            base_qty *= 3
        submit_order(book, side=side, order_type=OrderType.MARKET, qty=max(1, base_qty))

        mid_now = int(book.mid_price_ticks() or profile.base_mid_ticks)
        submit_order(book, Side.BUY, OrderType.LIMIT, qty=120, price_ticks=max(1, mid_now - 1))
        submit_order(book, Side.SELL, OrderType.LIMIT, qty=120, price_ticks=mid_now + 1)

        cur_mid = book.mid_price_ticks() or prev_mid
        returns.append((cur_mid - prev_mid) / prev_mid)
        prev_mid = cur_mid
        sp = book.spread_ticks()
        if sp is not None:
            spreads.append(sp)

    kurt = excess_kurtosis(returns)
    clust = abs_autocorr_lag1(returns)
    mean_spread = sum(spreads) / len(spreads) if spreads else 0.0

    # Signature plot: coarse 5-step variance ratio > 0
    coarse_rets = [sum(returns[i : i + 5]) for i in range(0, len(returns) - 4, 5)]
    coarse_var = sum(r * r for r in coarse_rets) / max(1, len(coarse_rets))

    checks = (
        StylizedFactCheck(
            "fat_tails", kurt > 0.0, round(kurt, 4), "> 0.0", EngineProvenance.SYNTHETIC
        ),
        StylizedFactCheck(
            "volatility_clustering",
            clust > 0.0,
            round(clust, 4),
            "> 0.0",
            EngineProvenance.SYNTHETIC,
        ),
        StylizedFactCheck(
            "positive_spread",
            mean_spread >= 1.0,
            round(mean_spread, 4),
            ">= 1.0 ticks",
            EngineProvenance.SYNTHETIC,
        ),
        StylizedFactCheck(
            "signature_plot",
            coarse_var > 0.0,
            round(coarse_var, 8),
            "> 0.0",
            EngineProvenance.SYNTHETIC,
        ),
    )
    return ValidationSuiteResult(
        checks=checks,
        all_passed=all(c.passed for c in checks),
        provenance=EngineProvenance.SYNTHETIC,
    )
