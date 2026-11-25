"""Multi-size, multi-strategy deterministic simulation runner (T1.8-T1.9)."""

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.impact import ExecutionStrategy, execute_parent_order
from opentrade.engine.metrics import ExecutionMetrics, compute_execution_metrics
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import EngineProvenance, get_profile


@dataclass(frozen=True)
class SizeSweepPoint:
    """Single (size, strategy) evaluation point in a simulation run."""

    size: int
    strategy: ExecutionStrategy
    metrics: ExecutionMetrics

    def to_dict(self) -> dict[str, Any]:
        """Serialize sweep point to a JSON-compatible dictionary."""
        return {
            "size": self.size,
            "strategy": self.strategy.value,
            "metrics": self.metrics.to_dict(),
        }


@dataclass(frozen=True)
class SimulationRunResult:
    """Immutable output of a multi-size, multi-strategy simulation sweep."""

    seed: int
    profile_id: str
    book_depth: int
    provenance: EngineProvenance
    points: tuple[SizeSweepPoint, ...]
    event_log_sha256: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize simulation run result to a JSON-compatible dictionary."""
        return {
            "seed": self.seed,
            "profile_id": self.profile_id,
            "book_depth": self.book_depth,
            "provenance": self.provenance.value,
            "points": [pt.to_dict() for pt in self.points],
            "event_log_sha256": self.event_log_sha256,
        }


def run_simulation(
    seed: int = 42,
    profile_id: str = "synthetic_default",
    sizes: tuple[int, ...] = (100, 500, 1000),
    book_depth: int = 10,
    strategies: tuple[ExecutionStrategy, ...] = (
        ExecutionStrategy.TWAP,
        ExecutionStrategy.VWAP,
        ExecutionStrategy.POV,
        ExecutionStrategy.IS,
    ),
    side: Side = Side.BUY,
) -> SimulationRunResult:
    """Execute a deterministic sweep across all configured sizes and strategies."""
    profile = get_profile(profile_id)
    points: list[SizeSweepPoint] = []
    point_hashes: list[str] = []

    for size in sizes:
        for strategy in strategies:
            book = OrderBook()
            rng = random.Random(seed)  # noqa: S311
            seed_initial_book(
                book,
                profile,
                rng=rng,
                depth_levels=max(book_depth, profile.initial_levels),
            )
            initial_spread = book.spread_ticks()
            exec_res = execute_parent_order(
                book=book,
                profile=profile,
                side=side,
                total_qty=size,
                strategy=strategy,
                num_slices=5,
                seed=seed,
                background_steps_per_slice=5,
            )
            metrics = compute_execution_metrics(exec_res, initial_spread_ticks=initial_spread)
            points.append(SizeSweepPoint(size=size, strategy=strategy, metrics=metrics))
            point_hashes.append(exec_res.event_log_sha256)

    agg_payload = json.dumps(point_hashes, separators=(",", ":")).encode("utf-8")
    agg_sha = hashlib.sha256(agg_payload).hexdigest()

    return SimulationRunResult(
        seed=seed,
        profile_id=profile.profile_id,
        book_depth=book_depth,
        provenance=profile.provenance,
        points=tuple(points),
        event_log_sha256=agg_sha,
    )
