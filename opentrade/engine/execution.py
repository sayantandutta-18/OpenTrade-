"""Comparative execution strategy runner and shortfall ranking (T13.1)."""

from dataclasses import dataclass

from opentrade.engine.book import Side
from opentrade.engine.impact import ExecutionStrategy
from opentrade.engine.profiles import EngineProvenance
from opentrade.engine.runner import run_simulation


@dataclass(frozen=True)
class StrategyRankEntry:
    """Ranked execution strategy performance summary."""

    rank: int
    strategy: ExecutionStrategy
    implementation_shortfall_bps: float
    temporary_impact_bps: float
    permanent_impact_bps: float
    fill_rate: float


@dataclass(frozen=True)
class ExecutionBenchmarkResult:
    """All strategies ranked ascending by implementation shortfall (T13.1)."""

    profile_id: str
    seed: int
    total_qty: int
    rankings: tuple[StrategyRankEntry, ...]
    provenance: EngineProvenance


def rank_execution_strategies(
    profile_id: str = "synthetic_default",
    seed: int = 42,
    total_qty: int = 1200,
    side: Side = Side.BUY,
) -> ExecutionBenchmarkResult:
    """Run TWAP, VWAP, POV, and IS for `total_qty` and rank by implementation shortfall."""
    sim = run_simulation(
        seed=seed,
        profile_id=profile_id,
        sizes=(total_qty,),
        book_depth=20,
        strategies=(
            ExecutionStrategy.TWAP,
            ExecutionStrategy.VWAP,
            ExecutionStrategy.POV,
            ExecutionStrategy.IS,
        ),
        side=side,
    )
    sorted_pts = sorted(sim.points, key=lambda p: p.metrics.implementation_shortfall_bps)
    rankings = tuple(
        StrategyRankEntry(
            rank=idx + 1,
            strategy=pt.strategy,
            implementation_shortfall_bps=pt.metrics.implementation_shortfall_bps,
            temporary_impact_bps=pt.metrics.temporary_impact_bps,
            permanent_impact_bps=pt.metrics.permanent_impact_bps,
            fill_rate=pt.metrics.fill_rate,
        )
        for idx, pt in enumerate(sorted_pts)
    )
    return ExecutionBenchmarkResult(
        profile_id=profile_id,
        seed=seed,
        total_qty=total_qty,
        rankings=rankings,
        provenance=sim.provenance,
    )
