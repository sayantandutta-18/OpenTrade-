"""Scheduled news/liquidity shock events in order flow (T9.1)."""

import random
from dataclasses import dataclass

from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.matching import cancel_order, submit_order
from opentrade.engine.order_flow import _step_event
from opentrade.engine.profiles import EngineProvenance, LiquidityProfile


@dataclass(frozen=True)
class ShockEvent:
    """Scheduled liquidity withdrawal and directional arrival shock."""

    step: int
    duration: int = 10
    arrival_multiplier: float = 3.0
    cancel_liquidity_frac: float = 0.5
    directional_side: Side | None = None
    directional_qty: int = 0


@dataclass(frozen=True)
class ShockFlowSummary:
    """Summary of an order-flow run containing scheduled shock events."""

    steps: int
    shock_events_triggered: int
    peak_spread_ticks: int
    total_volume: int
    event_log_sha256: str
    provenance: EngineProvenance


def run_shock_flow(
    book: OrderBook,
    profile: LiquidityProfile,
    seed: int,
    steps: int = 60,
    shocks: tuple[ShockEvent, ...] = (),
) -> ShockFlowSummary:
    """Run seeded order flow with scheduled shock events on `book` (T9.1)."""
    rng = random.Random(seed)  # noqa: S311
    shock_by_step = {s.step: s for s in shocks}
    active_until = -1
    triggered = 0
    peak_spread = book.spread_ticks() or 0
    total_volume = 0

    for step in range(steps):
        shock = shock_by_step.get(step)
        if shock is not None:
            triggered += 1
            active_until = max(active_until, step + shock.duration)
            resting = book.resting_order_ids()
            cancel_n = int(len(resting) * max(0.0, min(1.0, shock.cancel_liquidity_frac)))
            for oid in resting[:cancel_n]:
                cancel_order(book, oid)
            if shock.directional_side is not None and shock.directional_qty > 0:
                res = submit_order(
                    book,
                    side=shock.directional_side,
                    order_type=OrderType.MARKET,
                    qty=shock.directional_qty,
                )
                total_volume += res.filled_qty

        in_shock = step <= active_until
        sub_steps = 3 if in_shock else 1
        for _ in range(sub_steps):
            total_rate = profile.limit_rate + profile.market_rate + profile.cancel_rate
            draw = rng.random() * total_rate
            if draw < profile.limit_rate:
                _, vol = _step_event(book, profile, rng, "limit")
            elif draw < profile.limit_rate + profile.market_rate:
                _, vol = _step_event(book, profile, rng, "market")
            else:
                _, vol = _step_event(book, profile, rng, "cancel")
            total_volume += vol

        sp = book.spread_ticks()
        if sp is not None and sp > peak_spread:
            peak_spread = sp

    return ShockFlowSummary(
        steps=steps,
        shock_events_triggered=triggered,
        peak_spread_ticks=peak_spread,
        total_volume=total_volume,
        event_log_sha256=book.event_log_sha256(),
        provenance=profile.provenance,
    )
