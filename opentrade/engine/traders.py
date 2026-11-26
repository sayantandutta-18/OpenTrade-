"""Behavioral order generation for noise, momentum, and informed traders (T2.3)."""

import random
from dataclasses import dataclass
from enum import StrEnum

from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.order_flow import sample_power_law_distance
from opentrade.engine.profiles import LiquidityProfile


class TraderType(StrEnum):
    """Trader archetypes per docs/SRS.md FR-18."""

    NOISE = "NOISE"
    MOMENTUM = "MOMENTUM"
    INFORMED = "INFORMED"


@dataclass(frozen=True)
class TraderAction:
    """Order decision produced by a trader behavioral rule."""

    trader_type: TraderType
    side: Side
    order_type: OrderType
    qty: int
    price_ticks: int | None


def _passive_price(book: OrderBook, profile: LiquidityProfile, side: Side, offset: int) -> int:
    """Compute a passive limit price offset from the opposing quote or base mid."""
    mid_ref = int(book.mid_price_ticks() or profile.base_mid_ticks)
    if side is Side.BUY:
        opp = book.best_ask()
        return max(1, (opp - offset) if opp is not None else mid_ref - offset)
    opp = book.best_bid()
    return (opp + offset) if opp is not None else mid_ref + offset


def generate_noise_action(
    book: OrderBook,
    profile: LiquidityProfile,
    rng: random.Random,
) -> TraderAction:
    """Generate a random side and passive/aggressive order for a noise trader."""
    side = Side.BUY if rng.random() < 0.5 else Side.SELL
    is_market = rng.random() < 0.25
    qty = max(1, int(profile.level_qty * (0.05 + 0.15 * rng.random())))
    if is_market:
        return TraderAction(TraderType.NOISE, side, OrderType.MARKET, qty, None)
    offset = sample_power_law_distance(rng, profile.power_law_alpha, profile.initial_levels)
    return TraderAction(
        TraderType.NOISE,
        side,
        OrderType.LIMIT,
        qty,
        _passive_price(book, profile, side, offset),
    )


def generate_momentum_action(
    book: OrderBook,
    profile: LiquidityProfile,
    rng: random.Random,
    recent_return_ticks: int,
) -> TraderAction:
    """Generate an order following recent price direction (chases momentum)."""
    if recent_return_ticks > 0:
        side = Side.BUY
    elif recent_return_ticks < 0:
        side = Side.SELL
    else:
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
    qty = max(1, int(profile.level_qty * (0.10 + 0.20 * rng.random())))
    is_market = abs(recent_return_ticks) >= 2 or rng.random() < 0.5
    if is_market:
        return TraderAction(TraderType.MOMENTUM, side, OrderType.MARKET, qty, None)
    offset = sample_power_law_distance(rng, profile.power_law_alpha, profile.initial_levels)
    return TraderAction(
        TraderType.MOMENTUM,
        side,
        OrderType.LIMIT,
        qty,
        _passive_price(book, profile, side, offset),
    )


def generate_informed_action(
    book: OrderBook,
    profile: LiquidityProfile,
    rng: random.Random,
    true_direction: int,
    accuracy: float = 0.85,
) -> TraderAction:
    """Generate an order aligned with true_direction (+1/-1) with probability `accuracy`."""
    clamped_acc = max(0.0, min(1.0, accuracy))
    correct_side = Side.BUY if true_direction >= 0 else Side.SELL
    wrong_side = Side.SELL if correct_side is Side.BUY else Side.BUY
    side = correct_side if rng.random() < clamped_acc else wrong_side
    qty = max(1, int(profile.level_qty * (0.15 + 0.25 * rng.random())))
    # Informed traders preferentially take liquidity via market/IOC orders
    _ = book
    return TraderAction(TraderType.INFORMED, side, OrderType.MARKET, qty, None)
