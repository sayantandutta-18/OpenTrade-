"""Tests for market impact injection, sweep, log-log fit, and decay (T1.6, T3.1-T3.3).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-18, AC-19, AC-20) and docs/SRS.md (FR-22 to FR-25, FR-52).
"""

import random

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.impact import (
    ExecutionStrategy,
    compute_slice_schedule,
    execute_parent_order,
    inject_market_order,
)
from opentrade.engine.impact_analytics import (
    fit_power_law_log_log,
    measure_impact_decay,
    run_impact_sweep,
)
from opentrade.engine.invariants import check_book_invariants
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import EngineProvenance, get_profile


def test_slice_schedules_sum_to_total_qty_across_all_strategies() -> None:
    """FR-22, FR-25: TWAP, VWAP, POV, and IS schedules sum exactly to total_qty."""
    for strategy in ExecutionStrategy:
        sched = compute_slice_schedule(total_qty=1000, num_slices=5, strategy=strategy)
        assert len(sched) == 5
        assert sum(sched) == 1000
        assert all(q > 0 for q in sched)

    is_sched = compute_slice_schedule(total_qty=1000, num_slices=5, strategy=ExecutionStrategy.IS)
    assert is_sched[0] > is_sched[-1]


def test_execute_parent_order_across_strategies_and_provenance() -> None:
    """FR-22, FR-52: Executing parent orders across strategies preserves book invariants."""
    profile = get_profile("synthetic_default")
    for strategy in ExecutionStrategy:
        book = OrderBook()
        seed_initial_book(book, profile, random.Random(42))  # noqa: S311
        res = execute_parent_order(
            book=book,
            profile=profile,
            side=Side.BUY,
            total_qty=1500,
            strategy=strategy,
            num_slices=5,
            seed=42,
            background_steps_per_slice=10,
        )
        assert res.strategy is strategy
        assert res.total_filled_qty == 1500
        assert res.avg_fill_price_ticks >= res.arrival_mid_ticks
        assert res.provenance is EngineProvenance.SYNTHETIC
        assert len(res.slices) == 5
        check_book_invariants(book)


def test_inject_market_order_measures_arrival_mid_slippage_t3_1() -> None:
    """T3.1, FR-22: Market order injection measures slippage strictly against arrival mid."""
    profile = get_profile("synthetic_default")
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(42))  # noqa: S311
    pre_mid = book.mid_price_ticks()
    assert pre_mid is not None

    inj = inject_market_order(book, Side.BUY, qty=800, provenance=profile.provenance)
    assert inj.filled_qty == 800
    assert inj.arrival_mid_ticks == pre_mid
    assert inj.avg_fill_price_ticks > pre_mid
    assert inj.slippage_ticks > 0.0
    assert inj.slippage_bps > 0.0
    assert inj.provenance is EngineProvenance.SYNTHETIC
    check_book_invariants(book)


def test_fit_power_law_recovers_synthetic_exponent_t3_2() -> None:
    """T3.2, AC-19: Log-log OLS recovers known synthetic power-law exponent and 95% CI."""
    sizes = [100, 300, 1000, 3000, 6000, 10000]
    impacts = [0.8 * (s**0.5) for s in sizes]
    fit = fit_power_law_log_log(sizes, impacts)

    assert abs(fit.beta - 0.5) < 1e-6
    assert fit.r_squared > 0.9999
    assert fit.ci95_low <= fit.beta <= fit.ci95_high


def test_impact_sweep_default_profile_seed_42_ac18_ac19_ac20() -> None:
    """T3.2, AC-18, AC-19, AC-20: Default sweep produces >=6 sizes and exponent in [0.4, 0.6]."""
    sweep = run_impact_sweep(profile_id="synthetic_default", seed=42)
    assert len(sweep.points) >= 6
    assert sweep.points[0].size <= 100
    assert sweep.points[-1].size >= 10_000 or sweep.book_capped
    assert sweep.fit.ci95_low <= sweep.fit.beta <= sweep.fit.ci95_high
    assert 0.4 <= sweep.fit.beta <= 0.6
    assert sweep.provenance is EngineProvenance.SYNTHETIC


def test_impact_decay_separates_temporary_and_permanent_t3_3() -> None:
    """T3.3, FR-25, FR-52: Decay curve separates peak, temporary, and permanent impact."""
    decay = measure_impact_decay(
        profile_id="synthetic_default",
        seed=42,
        qty=2500,
        side=Side.BUY,
        relaxation_steps=40,
        sample_every=5,
    )
    assert decay.peak_impact_bps > 0.0
    assert len(decay.curve) >= 2
    assert decay.curve[0].step == 0
    assert (
        abs((decay.temporary_impact_bps + decay.permanent_impact_bps) - decay.peak_impact_bps)
        < 1e-9
    )
    assert decay.provenance is EngineProvenance.SYNTHETIC
