"""Tests for noise, momentum, and informed trader types (T2.3).

Follows docs/SRS.md (FR-18, FR-52) and docs/TASKS.md (T2.3).
"""

import random

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import get_profile
from opentrade.engine.traders import (
    TraderType,
    generate_informed_action,
    generate_momentum_action,
    generate_noise_action,
)


def test_noise_trader_places_both_sides_randomly() -> None:
    """T2.3, FR-18: Noise trader generates both BUY and SELL orders using injected RNG."""
    profile = get_profile("synthetic_default")
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(42))  # noqa: S311

    rng = random.Random(10)  # noqa: S311
    actions = [generate_noise_action(book, profile, rng) for _ in range(100)]
    buys = sum(1 for a in actions if a.side is Side.BUY)
    sells = sum(1 for a in actions if a.side is Side.SELL)

    assert all(a.trader_type is TraderType.NOISE for a in actions)
    assert buys > 25 and sells > 25
    assert all(a.qty > 0 for a in actions)


def test_momentum_trader_follows_recent_price_direction() -> None:
    """T2.3, FR-18: Momentum trader buys after positive return and sells after negative return."""
    profile = get_profile("synthetic_default")
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(42))  # noqa: S311
    rng = random.Random(11)  # noqa: S311

    up_action = generate_momentum_action(book, profile, rng, recent_return_ticks=5)
    assert up_action.trader_type is TraderType.MOMENTUM
    assert up_action.side is Side.BUY

    down_action = generate_momentum_action(book, profile, rng, recent_return_ticks=-5)
    assert down_action.trader_type is TraderType.MOMENTUM
    assert down_action.side is Side.SELL


def test_informed_trader_respects_accuracy_parameter() -> None:
    """T2.3, FR-18: Informed trader matches true_direction at configured accuracy rate."""
    profile = get_profile("synthetic_default")
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(42))  # noqa: S311

    rng = random.Random(12)  # noqa: S311
    actions = [
        generate_informed_action(book, profile, rng, true_direction=1, accuracy=0.85)
        for _ in range(400)
    ]
    assert all(a.trader_type is TraderType.INFORMED for a in actions)
    buy_rate = sum(1 for a in actions if a.side is Side.BUY) / len(actions)
    assert 0.78 <= buy_rate <= 0.92
