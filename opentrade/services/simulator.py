"""Simulator preview service bridging UI and engine (T3.5)."""

import random
from typing import Any

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.impact import inject_market_order
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import PRESET_PROFILES, get_profile
from opentrade.engine.validation import run_stylized_fact_validation


def list_available_profiles() -> list[str]:
    """Return available preset liquidity profile IDs for UI selection."""
    return list(PRESET_PROFILES.keys())


def preview_book_and_inject(
    profile_id: str,
    seed: int,
    side: str = "BUY",
    qty: int = 100,
    levels: int = 10,
) -> dict[str, Any]:
    """Seed a book from profile + seed, inject a market order, and return display snapshot."""
    profile = get_profile(profile_id)
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(seed))  # noqa: S311
    parsed_side = Side(side.upper())
    inj_dict: dict[str, Any] | None = None
    if qty > 0:
        inj = inject_market_order(book, side=parsed_side, qty=qty, provenance=profile.provenance)
        inj_dict = {
            "side": inj.side.value,
            "requested_qty": inj.requested_qty,
            "filled_qty": inj.filled_qty,
            "arrival_mid_ticks": inj.arrival_mid_ticks,
            "avg_fill_price_ticks": inj.avg_fill_price_ticks,
            "slippage_ticks": inj.slippage_ticks,
            "slippage_bps": inj.slippage_bps,
        }
    bids, asks = book.depth_snapshot(levels=levels)

    return {
        "profile_id": profile.profile_id,
        "provenance": profile.provenance.value,
        "tick_size": profile.tick_size,
        "best_bid": book.best_bid(),
        "best_ask": book.best_ask(),
        "spread_ticks": book.spread_ticks(),
        "mid_price_ticks": book.mid_price_ticks(),
        "bids": [
            {"price_ticks": lvl.price_ticks, "qty": lvl.total_qty, "orders": lvl.order_count}
            for lvl in bids
        ],
        "asks": [
            {"price_ticks": lvl.price_ticks, "qty": lvl.total_qty, "orders": lvl.order_count}
            for lvl in asks
        ],
        "injection": inj_dict,
    }


def run_validation_service(profile_id: str, seed: int = 42, steps: int = 400) -> dict[str, Any]:
    """Run stylized-fact validation for UI display without exposing engine internals (T18.1)."""
    res = run_stylized_fact_validation(profile_id=profile_id, seed=seed, steps=steps)
    return {
        "profile_id": profile_id,
        "seed": seed,
        "provenance": res.provenance.value,
        "all_passed": res.all_passed,
        "checks": [
            {"name": c.name, "passed": c.passed, "value": c.value, "threshold": c.threshold}
            for c in res.checks
        ],
    }
