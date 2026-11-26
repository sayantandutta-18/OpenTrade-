"""Multi-book cross-impact and emergent return correlation (T15.1)."""

import math
import random
from dataclasses import dataclass

from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.matching import submit_order
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import EngineProvenance, get_profile


@dataclass(frozen=True)
class CrossImpactResult:
    """Emergent return series and Pearson correlation from coupled order books."""

    returns_a: tuple[float, ...]
    returns_b: tuple[float, ...]
    emergent_correlation: float
    provenance: EngineProvenance


def _pearson_corr(xs: list[float], ys: list[float]) -> float:
    """Compute sample Pearson correlation between two equal-length series."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0


def simulate_coupled_books(
    steps: int = 120,
    cross_impact_beta: float = 0.8,
    seed: int = 42,
) -> CrossImpactResult:
    """Simulate two order books where flow in Book A propagates cross-impact to Book B."""
    profile = get_profile("thin_book")
    rng = random.Random(seed)  # noqa: S311

    book_a = OrderBook()
    book_b = OrderBook()
    seed_initial_book(book_a, profile, random.Random(seed), depth_levels=30)  # noqa: S311
    seed_initial_book(book_b, profile, random.Random(seed + 1), depth_levels=30)  # noqa: S311

    prev_a = book_a.mid_price_ticks() or float(profile.base_mid_ticks)
    prev_b = book_b.mid_price_ticks() or float(profile.base_mid_ticks)
    rets_a: list[float] = []
    rets_b: list[float] = []

    for _ in range(steps):
        side_a = Side.BUY if rng.random() < 0.5 else Side.SELL
        qty_a = rng.randint(150, 350)
        submit_order(book_a, side=side_a, order_type=OrderType.MARKET, qty=qty_a)

        mid_a_now = int(book_a.mid_price_ticks() or profile.base_mid_ticks)
        submit_order(book_a, Side.BUY, OrderType.LIMIT, qty=80, price_ticks=max(1, mid_a_now - 2))
        submit_order(book_a, Side.SELL, OrderType.LIMIT, qty=80, price_ticks=mid_a_now + 2)

        if cross_impact_beta > 0.0:
            cross_qty = max(1, int(qty_a * cross_impact_beta))
            submit_order(book_b, side=side_a, order_type=OrderType.MARKET, qty=cross_qty)

        side_b_noise = Side.BUY if rng.random() < 0.5 else Side.SELL
        submit_order(
            book_b, side=side_b_noise, order_type=OrderType.MARKET, qty=rng.randint(30, 80)
        )
        mid_b_now = int(book_b.mid_price_ticks() or profile.base_mid_ticks)
        submit_order(book_b, Side.BUY, OrderType.LIMIT, qty=80, price_ticks=max(1, mid_b_now - 2))
        submit_order(book_b, Side.SELL, OrderType.LIMIT, qty=80, price_ticks=mid_b_now + 2)

        cur_a = book_a.mid_price_ticks() or prev_a
        cur_b = book_b.mid_price_ticks() or prev_b
        rets_a.append((cur_a - prev_a) / prev_a)
        rets_b.append((cur_b - prev_b) / prev_b)
        prev_a, prev_b = cur_a, cur_b

    return CrossImpactResult(
        returns_a=tuple(rets_a),
        returns_b=tuple(rets_b),
        emergent_correlation=_pearson_corr(rets_a, rets_b),
        provenance=EngineProvenance.SYNTHETIC,
    )
