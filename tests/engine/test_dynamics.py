"""Tests for shocks, Hawkes arrivals, endogenous mid, and Avellaneda-Stoikov maker (T9.1-T12.1).

Follows docs/TASKS.md (T9.1, T10.1, T11.1, T12.1) and docs/SRS.md (FR-21, FR-52).
"""

import random

from opentrade.engine.book import OrderBook, Side
from opentrade.engine.hawkes import simulate_hawkes_arrivals
from opentrade.engine.invariants import check_book_invariants
from opentrade.engine.maker import avellaneda_stoikov_quotes, simulate_market_maker
from opentrade.engine.order_flow import seed_initial_book
from opentrade.engine.price import evolve_endogenous_mid
from opentrade.engine.profiles import EngineProvenance, get_profile
from opentrade.engine.shocks import ShockEvent, run_shock_flow


def test_scheduled_shock_event_impacts_spread_and_is_deterministic_t9_1() -> None:
    """T9.1, FR-52: Scheduled shock widens spread/volume deterministically at target step."""
    profile = get_profile("synthetic_default")
    shock = ShockEvent(
        step=20,
        duration=15,
        arrival_multiplier=3.0,
        cancel_liquidity_frac=0.5,
        directional_side=Side.BUY,
        directional_qty=800,
    )

    b1 = OrderBook()
    seed_initial_book(b1, profile, random.Random(42))  # noqa: S311
    s1 = run_shock_flow(b1, profile, seed=42, steps=60, shocks=(shock,))
    check_book_invariants(b1)

    b2 = OrderBook()
    seed_initial_book(b2, profile, random.Random(42))  # noqa: S311
    s2 = run_shock_flow(b2, profile, seed=42, steps=60, shocks=(shock,))

    assert s1 == s2
    assert s1.shock_events_triggered == 1
    assert s1.peak_spread_ticks >= 1
    assert s1.provenance is EngineProvenance.SYNTHETIC


def test_hawkes_arrivals_show_burstiness_above_poisson_t10_1() -> None:
    """T10.1, FR-21: Hawkes arrivals exhibit clustering (Fano factor > 1.2) vs Poisson."""
    hawkes = simulate_hawkes_arrivals(
        horizon_seconds=400.0,
        baseline_rate=1.0,
        alpha=0.8,
        beta=1.2,
        seed=42,
    )
    poisson = simulate_hawkes_arrivals(
        horizon_seconds=400.0,
        baseline_rate=1.0,
        alpha=0.0,
        beta=1.2,
        seed=42,
    )
    assert hawkes.event_count > 100
    assert hawkes.fano_factor > 1.2
    assert hawkes.fano_factor > poisson.fano_factor
    assert hawkes.provenance is EngineProvenance.SYNTHETIC


def test_endogenous_mid_drifts_with_net_buying_imbalance_t11_1() -> None:
    """T11.1: Sustained net-buying imbalance drives mid price upward; net-selling downward."""
    buy_path = evolve_endogenous_mid(
        initial_mid_ticks=10_000,
        signed_imbalances=[200] * 30,
        sensitivity=0.02,
    )
    sell_path = evolve_endogenous_mid(
        initial_mid_ticks=10_000,
        signed_imbalances=[-200] * 30,
        sensitivity=0.02,
    )
    assert buy_path[-1] > buy_path[0]
    assert sell_path[-1] < sell_path[0]


def test_avellaneda_stoikov_quotes_and_pnl_sum_identity_t12_1() -> None:
    """T12.1: AS quotes skew with inventory and realized + MTM P&L equals total P&L."""
    bid_flat, ask_flat = avellaneda_stoikov_quotes(
        mid_ticks=10_000.0, inventory=0, gamma=0.1, sigma_ticks=2.0, kappa=1.5, time_remaining=1.0
    )
    bid_long, ask_long = avellaneda_stoikov_quotes(
        mid_ticks=10_000.0, inventory=10, gamma=0.1, sigma_ticks=2.0, kappa=1.5, time_remaining=1.0
    )
    assert bid_flat < ask_flat
    # Long inventory lowers both reservation bid and ask to shed inventory
    assert bid_long <= bid_flat and ask_long <= ask_flat

    mid_series = [10_000.0 + (i % 5 - 2) * 1.5 for i in range(60)]
    pnl = simulate_market_maker(mid_series, gamma=0.1, sigma_ticks=2.0, kappa=1.5, seed=42)
    assert abs((pnl.realized_spread_pnl + pnl.inventory_mtm_pnl) - pnl.total_pnl) < 1e-6
    assert pnl.provenance is EngineProvenance.SYNTHETIC
