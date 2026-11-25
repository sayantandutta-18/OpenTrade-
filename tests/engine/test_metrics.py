"""Tests for execution metrics and slippage attribution (T1.7).

Follows docs/SRS.md (FR-22, FR-25, FR-52) and docs/CODING_STANDARDS.md (§8).
"""

import random

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.impact import ExecutionStrategy, execute_parent_order
from opentrade.engine.metrics import compute_execution_metrics
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import EngineProvenance, get_profile


def test_execution_metrics_attribution_and_provenance() -> None:
    """FR-22, FR-25, FR-52: Metrics compute shortfall, temporary/permanent impact, fill rate."""
    profile = get_profile("synthetic_default")
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(42))  # noqa: S311
    initial_spread = book.spread_ticks()

    res = execute_parent_order(
        book=book,
        profile=profile,
        side=Side.BUY,
        total_qty=2000,
        strategy=ExecutionStrategy.TWAP,
        num_slices=5,
        seed=42,
        background_steps_per_slice=10,
    )
    metrics = compute_execution_metrics(res, initial_spread_ticks=initial_spread)

    assert metrics.arrival_price_ticks == res.arrival_mid_ticks
    assert metrics.avg_execution_price_ticks == res.avg_fill_price_ticks
    assert metrics.fill_rate == 1.0
    assert metrics.implementation_shortfall_bps > 0.0
    assert metrics.spread_cost_bps >= 0.0
    assert (
        abs(
            (metrics.temporary_impact_bps + metrics.permanent_impact_bps)
            - metrics.implementation_shortfall_bps
        )
        < 1e-9
    )
    assert metrics.provenance is EngineProvenance.SYNTHETIC

    as_dict = metrics.to_dict()
    assert as_dict["provenance"] == "SYNTHETIC"
