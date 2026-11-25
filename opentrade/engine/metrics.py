"""Execution metrics and slippage attribution (T1.7)."""

from dataclasses import dataclass
from typing import Any

from opentrade.engine.book import Side
from opentrade.engine.impact import ImpactExecutionResult
from opentrade.engine.profiles import EngineProvenance


@dataclass(frozen=True)
class ExecutionMetrics:
    """Immutable slippage and market impact attribution metrics."""

    arrival_price_ticks: float
    avg_execution_price_ticks: float
    vwap_benchmark_ticks: float
    implementation_shortfall_bps: float
    temporary_impact_bps: float
    permanent_impact_bps: float
    spread_cost_bps: float
    fill_rate: float
    provenance: EngineProvenance

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to a JSON-compatible dictionary preserving provenance."""
        return {
            "arrival_price_ticks": self.arrival_price_ticks,
            "avg_execution_price_ticks": self.avg_execution_price_ticks,
            "vwap_benchmark_ticks": self.vwap_benchmark_ticks,
            "implementation_shortfall_bps": self.implementation_shortfall_bps,
            "temporary_impact_bps": self.temporary_impact_bps,
            "permanent_impact_bps": self.permanent_impact_bps,
            "spread_cost_bps": self.spread_cost_bps,
            "fill_rate": self.fill_rate,
            "provenance": self.provenance.value,
        }


def compute_execution_metrics(
    result: ImpactExecutionResult,
    initial_spread_ticks: int | None = None,
) -> ExecutionMetrics:
    """Compute implementation shortfall, impact decomposition, and fill rate in bps."""
    arrival = result.arrival_mid_ticks
    sign = 1.0 if result.side is Side.BUY else -1.0

    if arrival <= 0.0:
        raise ValueError("arrival_mid_ticks must be positive")

    all_fills = [f for s in result.slices for f in s.fills]
    total_qty = sum(f.qty for f in all_fills)
    vwap = sum(f.price_ticks * f.qty for f in all_fills) / total_qty if total_qty > 0 else arrival

    shortfall_bps = sign * ((result.avg_fill_price_ticks - arrival) / arrival) * 10_000.0
    permanent_bps = sign * ((result.post_trade_mid_ticks - arrival) / arrival) * 10_000.0
    temporary_bps = shortfall_bps - permanent_bps
    spread_bps = (
        ((initial_spread_ticks / 2.0) / arrival) * 10_000.0
        if initial_spread_ticks is not None and initial_spread_ticks >= 0
        else 0.0
    )
    fill_rate = (
        result.total_filled_qty / result.total_target_qty if result.total_target_qty > 0 else 0.0
    )

    return ExecutionMetrics(
        arrival_price_ticks=arrival,
        avg_execution_price_ticks=result.avg_fill_price_ticks,
        vwap_benchmark_ticks=vwap,
        implementation_shortfall_bps=shortfall_bps,
        temporary_impact_bps=temporary_bps,
        permanent_impact_bps=permanent_bps,
        spread_cost_bps=spread_bps,
        fill_rate=fill_rate,
        provenance=result.provenance,
    )
