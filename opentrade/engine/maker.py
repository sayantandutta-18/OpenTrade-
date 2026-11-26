"""Avellaneda-Stoikov market maker with inventory skew and P&L split (T12.1)."""

import math
import random
from dataclasses import dataclass

from opentrade.engine.profiles import EngineProvenance


@dataclass(frozen=True)
class MakerPnLResult:
    """Market-maker P&L decomposed into realized spread + inventory mark-to-market."""

    final_inventory: int
    realized_spread_pnl: float
    inventory_mtm_pnl: float
    total_pnl: float
    fill_count: int
    provenance: EngineProvenance


def avellaneda_stoikov_quotes(
    mid_ticks: float,
    inventory: int,
    gamma: float,
    sigma_ticks: float,
    kappa: float,
    time_remaining: float,
) -> tuple[int, int]:
    """Compute Avellaneda-Stoikov reservation price and optimal integer bid/ask ticks."""
    if gamma <= 0 or kappa <= 0 or sigma_ticks < 0 or time_remaining < 0:
        raise ValueError("Invalid Avellaneda-Stoikov parameters")

    var_t = (sigma_ticks**2) * time_remaining
    reservation = mid_ticks - inventory * gamma * var_t
    half_spread = (gamma * var_t) / 2.0 + (1.0 / gamma) * math.log(1.0 + gamma / kappa)

    bid = max(1, round(reservation - half_spread))
    ask = max(bid + 1, round(reservation + half_spread))
    return bid, ask


def simulate_market_maker(
    mid_series: list[float],
    gamma: float = 0.1,
    sigma_ticks: float = 1.5,
    kappa: float = 1.5,
    seed: int = 42,
) -> MakerPnLResult:
    """Simulate Avellaneda-Stoikov quoting over `mid_series` with exact P&L identity."""
    if not mid_series:
        raise ValueError("mid_series cannot be empty")

    rng = random.Random(seed)  # noqa: S311
    n = len(mid_series)
    inventory = 0
    cash = 0.0
    realized_spread_pnl = 0.0
    inventory_mtm_pnl = 0.0
    fill_count = 0
    prev_mid = mid_series[0]

    for idx, mid in enumerate(mid_series):
        # Mark-to-market existing inventory across mid-price change
        inventory_mtm_pnl += inventory * (mid - prev_mid)
        prev_mid = mid

        tau = max(0.01, (n - idx) / n)
        bid, ask = avellaneda_stoikov_quotes(mid, inventory, gamma, sigma_ticks, kappa, tau)

        # Arrival probabilities decay exponentially with distance from mid
        prob_bid = min(0.8, math.exp(-0.4 * max(0.0, mid - bid)))
        prob_ask = min(0.8, math.exp(-0.4 * max(0.0, ask - mid)))

        if rng.random() < prob_bid:
            inventory += 1
            cash -= bid
            realized_spread_pnl += mid - bid
            fill_count += 1
        if rng.random() < prob_ask:
            inventory -= 1
            cash += ask
            realized_spread_pnl += ask - mid
            fill_count += 1

    total_pnl = cash + inventory * mid_series[-1]
    return MakerPnLResult(
        final_inventory=inventory,
        realized_spread_pnl=realized_spread_pnl,
        inventory_mtm_pnl=inventory_mtm_pnl,
        total_pnl=total_pnl,
        fill_count=fill_count,
        provenance=EngineProvenance.SYNTHETIC,
    )
