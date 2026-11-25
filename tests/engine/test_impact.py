"""Tests for market impact execution strategies (T1.6).

Follows docs/SRS.md (FR-22, FR-25, FR-52) and docs/TRD.md.
"""

import random

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.impact import (
    ExecutionStrategy,
    compute_slice_schedule,
    execute_parent_order,
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

    # IS (Almgren-Chriss) front-loads execution compared to TWAP
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
