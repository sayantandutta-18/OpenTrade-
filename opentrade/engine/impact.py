"""Market impact execution engine across TWAP, VWAP, POV, and IS strategies (T1.6)."""

import math
from dataclasses import dataclass
from enum import StrEnum

from opentrade.engine.book import Fill, OrderBook, OrderType, Side
from opentrade.engine.matching import submit_order
from opentrade.engine.order_flow import generate_order_flow
from opentrade.engine.profiles import EngineProvenance, LiquidityProfile


class ExecutionStrategy(StrEnum):
    """Supported parent-order execution algorithms."""

    TWAP = "TWAP"
    VWAP = "VWAP"
    POV = "POV"
    IS = "IS"


@dataclass(frozen=True)
class SliceExecution:
    """Result of executing one child slice against the live order book."""

    slice_index: int
    target_qty: int
    filled_qty: int
    avg_price_ticks: float
    pre_mid_ticks: float
    post_mid_ticks: float
    fills: tuple[Fill, ...]


@dataclass(frozen=True)
class InjectionResult:
    """Result of injecting a single market order against an active book (T3.1)."""

    side: Side
    requested_qty: int
    filled_qty: int
    arrival_mid_ticks: float
    avg_fill_price_ticks: float
    slippage_ticks: float
    slippage_bps: float
    post_mid_ticks: float
    fills: tuple[Fill, ...]
    provenance: EngineProvenance


def inject_market_order(
    book: OrderBook,
    side: Side,
    qty: int,
    provenance: EngineProvenance = EngineProvenance.SYNTHETIC,
) -> InjectionResult:
    """Inject a market order and measure slippage strictly against arrival mid (T3.1)."""
    arrival_mid = book.mid_price_ticks()
    if arrival_mid is None or arrival_mid <= 0.0:
        raise ValueError("Cannot measure arrival mid slippage on an empty book")

    res = submit_order(book, side=side, order_type=OrderType.MARKET, qty=qty)
    post_mid = book.mid_price_ticks() or arrival_mid

    if res.filled_qty > 0:
        notional = sum(f.price_ticks * f.qty for f in res.fills)
        avg_fill = notional / res.filled_qty
    else:
        avg_fill = arrival_mid

    sign = 1.0 if side is Side.BUY else -1.0
    slippage_ticks = sign * (avg_fill - arrival_mid)
    slippage_bps = (slippage_ticks / arrival_mid) * 10_000.0

    return InjectionResult(
        side=side,
        requested_qty=qty,
        filled_qty=res.filled_qty,
        arrival_mid_ticks=arrival_mid,
        avg_fill_price_ticks=avg_fill,
        slippage_ticks=slippage_ticks,
        slippage_bps=slippage_bps,
        post_mid_ticks=post_mid,
        fills=res.fills,
        provenance=provenance,
    )


@dataclass(frozen=True)
class ImpactExecutionResult:
    """Aggregated execution result for a sliced parent order."""

    strategy: ExecutionStrategy
    side: Side
    total_target_qty: int
    total_filled_qty: int
    arrival_mid_ticks: float
    post_trade_mid_ticks: float
    avg_fill_price_ticks: float
    slices: tuple[SliceExecution, ...]
    provenance: EngineProvenance
    event_log_sha256: str


def _allocate_weights(total_qty: int, weights: list[float]) -> list[int]:
    """Convert positive weights into integer slice quantities summing to total_qty."""
    weight_sum = sum(weights)
    raw = [total_qty * w / weight_sum for w in weights]
    counts = [int(x) for x in raw]
    remainder = total_qty - sum(counts)
    # Distribute rounding remainder deterministically to largest fractional parts
    order = sorted(range(len(weights)), key=lambda i: raw[i] - counts[i], reverse=True)
    for idx in order[:remainder]:
        counts[idx] += 1
    return [max(1, c) if total_qty >= len(weights) else c for c in counts]


def compute_slice_schedule(
    total_qty: int,
    num_slices: int,
    strategy: ExecutionStrategy,
    pov_rate: float = 0.25,
) -> list[int]:
    """Compute integer child-slice quantities summing exactly to total_qty."""
    if total_qty <= 0 or num_slices <= 0:
        raise ValueError("total_qty and num_slices must be positive integers")

    if strategy is ExecutionStrategy.TWAP:
        weights = [1.0] * num_slices
    elif strategy is ExecutionStrategy.VWAP:
        # U-shaped intraday volume profile
        weights = [
            1.0 + 0.6 * ((2.0 * i / max(1, num_slices - 1) - 1.0) ** 2) for i in range(num_slices)
        ]
    elif strategy is ExecutionStrategy.POV:
        rate = max(0.05, min(0.95, pov_rate))
        weights = [rate * (1.0 - 0.05 * i) for i in range(num_slices)]
    else:  # ExecutionStrategy.IS (Almgren-Chriss front-loaded decay)
        weights = [math.exp(-0.35 * i) for i in range(num_slices)]

    return _allocate_weights(total_qty, weights)


def execute_parent_order(
    book: OrderBook,
    profile: LiquidityProfile,
    side: Side,
    total_qty: int,
    strategy: ExecutionStrategy,
    num_slices: int = 5,
    seed: int = 42,
    background_steps_per_slice: int = 10,
) -> ImpactExecutionResult:
    """Slice and execute a parent order against `book` with optional background flow."""
    arrival_mid = book.mid_price_ticks() or float(profile.base_mid_ticks)
    schedule = compute_slice_schedule(total_qty=total_qty, num_slices=num_slices, strategy=strategy)

    slices: list[SliceExecution] = []
    total_filled = 0
    total_notional = 0

    for idx, slice_qty in enumerate(schedule):
        if slice_qty <= 0:
            continue
        pre_mid = book.mid_price_ticks() or arrival_mid
        res = submit_order(book, side=side, order_type=OrderType.MARKET, qty=slice_qty)
        post_mid = book.mid_price_ticks() or pre_mid

        slice_notional = sum(f.price_ticks * f.qty for f in res.fills)
        avg_slice_px = slice_notional / res.filled_qty if res.filled_qty > 0 else pre_mid
        total_filled += res.filled_qty
        total_notional += slice_notional

        slices.append(
            SliceExecution(
                slice_index=idx,
                target_qty=slice_qty,
                filled_qty=res.filled_qty,
                avg_price_ticks=avg_slice_px,
                pre_mid_ticks=pre_mid,
                post_mid_ticks=post_mid,
                fills=res.fills,
            )
        )

        if background_steps_per_slice > 0 and idx < len(schedule) - 1:
            generate_order_flow(
                book, profile, seed=seed + idx + 1, steps=background_steps_per_slice
            )

    post_trade_mid = book.mid_price_ticks() or arrival_mid
    avg_fill_px = total_notional / total_filled if total_filled > 0 else arrival_mid

    return ImpactExecutionResult(
        strategy=strategy,
        side=side,
        total_target_qty=total_qty,
        total_filled_qty=total_filled,
        arrival_mid_ticks=arrival_mid,
        post_trade_mid_ticks=post_trade_mid,
        avg_fill_price_ticks=avg_fill_px,
        slices=tuple(slices),
        provenance=profile.provenance,
        event_log_sha256=book.event_log_sha256(),
    )
