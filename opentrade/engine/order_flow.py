"""Deterministic synthetic order-flow generator with Poisson arrivals and power-law placement."""

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
    avg_spread_ticks: float
    avg_top_depth: float
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


def sample_power_law_distance(rng: random.Random, alpha: float, max_distance: int) -> int:
    """Sample an integer tick distance in [1, max_distance] with P(d) ~ d^(-alpha)."""
    if max_distance <= 1:
        return 1
    weights = [d ** (-max(0.1, alpha)) for d in range(1, max_distance + 1)]
    return rng.choices(range(1, max_distance + 1), weights=weights, k=1)[0]


def _step_event(
    book: OrderBook,
    profile: LiquidityProfile,
    rng: random.Random,
    event_kind: str,
) -> tuple[int, int]:
    """Execute one limit, market, or cancel event; returns (fills, volume)."""
    mid_ref = int(book.mid_price_ticks() or profile.base_mid_ticks)
    side = Side.BUY if rng.random() < 0.5 else Side.SELL

    if event_kind == "limit":
        offset = sample_power_law_distance(rng, profile.power_law_alpha, profile.initial_levels)
        best_opp = book.best_ask() if side is Side.BUY else book.best_bid()
        if side is Side.BUY:
            price = max(1, (best_opp - offset) if best_opp is not None else mid_ref - offset)
        else:
            price = (best_opp + offset) if best_opp is not None else mid_ref + offset
        qty = max(1, int(profile.level_qty * (0.05 + 0.15 * rng.random())))
        res = submit_order(book, side, OrderType.LIMIT, qty=qty, price_ticks=price)
        return len(res.fills), res.filled_qty

    if event_kind == "market":
        qty = max(1, int(profile.level_qty * (0.05 + 0.25 * rng.random())))
        res = submit_order(book, side, OrderType.MARKET, qty=qty)
        return len(res.fills), res.filled_qty

    resting_ids = book.resting_order_ids()
    if resting_ids:
        oid = rng.choice(resting_ids)
        cancel_order(book, oid)
    return 0, 0


def generate_order_flow(
    book: OrderBook,
    profile: LiquidityProfile,
    seed: int,
    steps: int = 200,
) -> OrderFlowSummary:
    """Run deterministic Poisson/Hawkes order flow on `book` using random.Random(seed)."""
    rng = random.Random(seed)  # noqa: S311
    limit_count = 0
    market_count = 0
    cancel_count = 0
    fill_count = 0
    total_volume = 0
    hawkes_boost = 0.0
    spread_sum = 0.0
    spread_obs = 0
    depth_sum = 0.0

    for _ in range(steps):
        eff_market = profile.market_rate * (1.0 + hawkes_boost)
        total_rate = profile.limit_rate + eff_market + profile.cancel_rate
        draw = rng.random() * total_rate

        if draw < profile.limit_rate:
            fills, vol = _step_event(book, profile, rng, "limit")
            limit_count += 1
            hawkes_boost *= 0.8
        elif draw < profile.limit_rate + eff_market:
            fills, vol = _step_event(book, profile, rng, "market")
            market_count += 1
            hawkes_boost = min(2.0, hawkes_boost * 0.8 + profile.hawkes_excitation)
        else:
            fills, vol = _step_event(book, profile, rng, "cancel")
            cancel_count += 1
            hawkes_boost *= 0.8

        fill_count += fills
        total_volume += vol
        sp = book.spread_ticks()
        if sp is not None:
            spread_sum += sp
            spread_obs += 1
        depth_sum += book.top_of_book_depth()

    avg_spread = spread_sum / spread_obs if spread_obs > 0 else 0.0
    avg_depth = depth_sum / steps if steps > 0 else 0.0
    return OrderFlowSummary(
        steps=steps,
        limit_count=limit_count,
        market_count=market_count,
        cancel_count=cancel_count,
        fill_count=fill_count,
        total_volume=total_volume,
        avg_spread_ticks=avg_spread,
        avg_top_depth=avg_depth,
        event_log_sha256=book.event_log_sha256(),
        provenance=profile.provenance,
    )


def run_poisson_horizon(
    book: OrderBook,
    profile: LiquidityProfile,
    seed: int,
    horizon_seconds: float = 100.0,
) -> OrderFlowSummary:
    """Simulate continuous-time Poisson arrivals over `horizon_seconds` (T2.1)."""
    rng = random.Random(seed)  # noqa: S311
    total_lam = profile.lambda_limit + profile.lambda_market + profile.lambda_cancel
    t = 0.0
    steps = 0
    limit_count = 0
    market_count = 0
    cancel_count = 0
    fill_count = 0
    total_volume = 0
    spread_sum = 0.0
    spread_obs = 0
    depth_sum = 0.0

    while total_lam > 0.0:
        t += rng.expovariate(total_lam)
        if t > horizon_seconds:
            break
        steps += 1
        draw = rng.random() * total_lam
        if draw < profile.lambda_limit:
            fills, vol = _step_event(book, profile, rng, "limit")
            limit_count += 1
        elif draw < profile.lambda_limit + profile.lambda_market:
            fills, vol = _step_event(book, profile, rng, "market")
            market_count += 1
        else:
            fills, vol = _step_event(book, profile, rng, "cancel")
            cancel_count += 1
        fill_count += fills
        total_volume += vol
        sp = book.spread_ticks()
        if sp is not None:
            spread_sum += sp
            spread_obs += 1
        depth_sum += book.top_of_book_depth()

    avg_spread = spread_sum / spread_obs if spread_obs > 0 else 0.0
    avg_depth = depth_sum / steps if steps > 0 else 0.0
    return OrderFlowSummary(
        steps=steps,
        limit_count=limit_count,
        market_count=market_count,
        cancel_count=cancel_count,
        fill_count=fill_count,
        total_volume=total_volume,
        avg_spread_ticks=avg_spread,
        avg_top_depth=avg_depth,
        event_log_sha256=book.event_log_sha256(),
        provenance=profile.provenance,
    )
