"""Deterministic synthetic order-flow generator (T1.5)."""

import random
from dataclasses import dataclass

from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.matching import cancel_order, submit_order
from opentrade.engine.profiles import EngineProvenance, LiquidityProfile


@dataclass(frozen=True)
class OrderFlowSummary:
    """Immutable summary of a synthetic order-flow simulation run."""

    steps: int
    limit_count: int
    market_count: int
    cancel_count: int
    fill_count: int
    total_volume: int
    event_log_sha256: str
    provenance: EngineProvenance


def seed_initial_book(
    book: OrderBook,
    profile: LiquidityProfile,
    rng: random.Random,
    depth_levels: int | None = None,
) -> list[int]:
    """Populate symmetric resting bid and ask levels around base_mid_ticks."""
    levels = depth_levels if depth_levels is not None else profile.initial_levels
    resting_ids: list[int] = []
    mid = profile.base_mid_ticks

    for offset in range(1, levels + 1):
        bid_qty = max(10, int(profile.level_qty * (0.8 + 0.4 * rng.random())))
        ask_qty = max(10, int(profile.level_qty * (0.8 + 0.4 * rng.random())))
        bid_res = submit_order(
            book, Side.BUY, OrderType.LIMIT, qty=bid_qty, price_ticks=mid - offset
        )
        ask_res = submit_order(
            book, Side.SELL, OrderType.LIMIT, qty=ask_qty, price_ticks=mid + offset
        )
        resting_ids.extend([bid_res.order_id, ask_res.order_id])

    return resting_ids


def _power_law_offset(rng: random.Random, alpha: float, max_offset: int) -> int:
    """Sample a positive integer tick offset using a bounded power-law draw."""
    raw = rng.paretovariate(max(0.5, alpha))
    return min(max_offset, max(1, int(raw)))


def generate_order_flow(
    book: OrderBook,
    profile: LiquidityProfile,
    seed: int,
    steps: int = 200,
) -> OrderFlowSummary:
    """Run deterministic Poisson/Hawkes order flow on `book` using random.Random(seed)."""
    rng = random.Random(seed)  # noqa: S311
    live_ids: list[int] = []
    limit_count = 0
    market_count = 0
    cancel_count = 0
    fill_count = 0
    total_volume = 0
    hawkes_boost = 0.0

    for _ in range(steps):
        eff_market = profile.market_rate * (1.0 + hawkes_boost)
        total_rate = profile.limit_rate + eff_market + profile.cancel_rate
        draw = rng.random() * total_rate

        mid_ref = int(book.mid_price_ticks() or profile.base_mid_ticks)
        side = Side.BUY if rng.random() < 0.5 else Side.SELL

        if draw < profile.limit_rate or (draw >= profile.limit_rate + eff_market and not live_ids):
            offset = _power_law_offset(rng, profile.power_law_alpha, profile.initial_levels)
            best_opp = book.best_ask() if side is Side.BUY else book.best_bid()
            if side is Side.BUY:
                price = max(1, (best_opp - offset) if best_opp is not None else mid_ref - offset)
            else:
                price = (best_opp + offset) if best_opp is not None else mid_ref + offset
            qty = max(1, int(profile.level_qty * (0.05 + 0.15 * rng.random())))
            res = submit_order(book, side, OrderType.LIMIT, qty=qty, price_ticks=price)
            limit_count += 1
            if res.status in ("RESTING", "PARTIAL") and book.get_order(res.order_id) is not None:
                live_ids.append(res.order_id)
            fill_count += len(res.fills)
            total_volume += res.filled_qty
            hawkes_boost *= 0.8
        elif draw < profile.limit_rate + eff_market:
            qty = max(1, int(profile.level_qty * (0.05 + 0.25 * rng.random())))
            res = submit_order(book, side, OrderType.MARKET, qty=qty)
            market_count += 1
            fill_count += len(res.fills)
            total_volume += res.filled_qty
            hawkes_boost = min(2.0, hawkes_boost * 0.8 + profile.hawkes_excitation)
        else:
            idx = rng.randrange(len(live_ids))
            oid = live_ids.pop(idx)
            if cancel_order(book, oid):
                cancel_count += 1
            hawkes_boost *= 0.8

    return OrderFlowSummary(
        steps=steps,
        limit_count=limit_count,
        market_count=market_count,
        cancel_count=cancel_count,
        fill_count=fill_count,
        total_volume=total_volume,
        event_log_sha256=book.event_log_sha256(),
        provenance=profile.provenance,
    )
