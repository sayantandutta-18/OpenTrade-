"""Historical replay service replaying real OHLCV bars through the order book (T20.3)."""

import random
from typing import Any

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.impact import inject_market_order
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.profiles import EngineProvenance, LiquidityProfile


def replay_historical_bars(
    symbol: str,
    bars: list[dict[str, Any]],
    qty: int = 200,
    side: str = "BUY",
    bar_label: str = "REAL",
    seed: int = 42,
) -> dict[str, Any]:
    """Replay historical OHLCV bars through seeded books with explicit provenance (T20.3)."""
    if not bars:
        raise ValueError("bars cannot be empty")
    clean_sym = symbol.strip().upper()
    parsed_side = Side(side.upper())

    steps: list[dict[str, Any]] = []
    for idx, bar in enumerate(bars):
        close_px = float(bar["close"])
        high_px = float(bar.get("high", close_px))
        low_px = float(bar.get("low", close_px))
        volume = max(1000.0, float(bar.get("volume", 500_000.0)))
        mid_ticks = max(100, round(close_px * 100.0))
        level_qty = max(100, int(volume * 0.001))
        spread_scale = max(1, round(((high_px - low_px) / max(1e-6, close_px)) * 100.0))

        prof = LiquidityProfile(
            profile_id=f"replay_{clean_sym}",
            provenance=EngineProvenance.CALIBRATED,
            base_mid_ticks=mid_ticks,
            initial_levels=15,
            level_qty=level_qty,
            volatility_ticks=spread_scale,
        )
        book = OrderBook()
        seed_initial_book(book, prof, random.Random(seed + idx))  # noqa: S311
        inj = inject_market_order(
            book, side=parsed_side, qty=qty, provenance=EngineProvenance.CALIBRATED
        )
        steps.append(
            {
                "date": str(bar["date"]),
                "close": close_px,
                "filled_qty": inj.filled_qty,
                "slippage_bps": round(inj.slippage_bps, 3),
                "bar_label": bar_label,
                "simulation_label": "CALIBRATED",
            }
        )

    return {
        "symbol": clean_sym,
        "bar_label": bar_label,
        "simulation_label": "CALIBRATED",
        "steps": steps,
    }
