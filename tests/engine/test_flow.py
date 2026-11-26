"""Tests for Poisson arrivals, power-law distances, and profile calibration (T2.1, T2.2, T2.4).

Follows docs/SRS.md (FR-15, FR-16, FR-17, FR-21, FR-37, FR-52) and docs/TASKS.md (T2.1-T2.4).
"""

import random

from opentrade.engine.book import OrderBook
from opentrade.engine.invariants import check_book_invariants
from opentrade.engine.order_flow import (
    generate_order_flow,
    run_poisson_horizon,
    sample_power_law_distance,
    seed_initial_book,
)
from opentrade.engine.profiles import EngineProvenance, get_profile


def test_order_flow_determinism_and_no_global_random_state() -> None:
    """AC-16, FR-15, FR-16: Identical seed produces identical flow and event_log_sha256."""
    profile = get_profile("synthetic_default")

    random.seed(999999)
    b1 = OrderBook()
    seed_initial_book(b1, profile, random.Random(42))  # noqa: S311
    s1 = generate_order_flow(b1, profile, seed=42, steps=150)

    random.seed(1)
    b2 = OrderBook()
    seed_initial_book(b2, profile, random.Random(42))  # noqa: S311
    s2 = generate_order_flow(b2, profile, seed=42, steps=150)

    assert s1 == s2
    assert s1.event_log_sha256 == b1.event_log_sha256()
    assert s1.provenance in (EngineProvenance.SYNTHETIC, EngineProvenance.CALIBRATED)
    check_book_invariants(b1)


def test_poisson_arrivals_match_configured_rates_t2_1() -> None:
    """T2.1, FR-16: Seeded Poisson horizon empirical rates match lambda_limit/market/cancel."""
    profile = get_profile("synthetic_default")
    book = OrderBook()
    seed_initial_book(book, profile, random.Random(42))  # noqa: S311

    horizon = 200.0
    summary = run_poisson_horizon(book, profile, seed=42, horizon_seconds=horizon)
    assert summary.steps > 0
    assert summary.provenance is EngineProvenance.SYNTHETIC
    check_book_invariants(book)

    emp_limit = summary.limit_count / horizon
    emp_market = summary.market_count / horizon
    emp_cancel = summary.cancel_count / horizon

    assert abs(emp_limit - profile.lambda_limit) < 0.20 * profile.lambda_limit + 0.25
    assert abs(emp_market - profile.lambda_market) < 0.25 * profile.lambda_market + 0.25
    assert abs(emp_cancel - profile.lambda_cancel) < 0.30 * profile.lambda_cancel + 0.25

    # Reproducibility check
    book2 = OrderBook()
    seed_initial_book(book2, profile, random.Random(42))  # noqa: S311
    summary2 = run_poisson_horizon(book2, profile, seed=42, horizon_seconds=horizon)
    assert summary == summary2


def test_power_law_placement_distances_distribution_t2_2() -> None:
    """T2.2, FR-17: Power-law placement concentrates near touch and decays with alpha."""
    rng_steep = random.Random(101)  # noqa: S311
    rng_flat = random.Random(101)  # noqa: S311

    steep_samples = [
        sample_power_law_distance(rng_steep, alpha=2.5, max_distance=25) for _ in range(2000)
    ]
    flat_samples = [
        sample_power_law_distance(rng_flat, alpha=1.1, max_distance=25) for _ in range(2000)
    ]

    assert all(1 <= d <= 25 for d in steep_samples)
    assert all(1 <= d <= 25 for d in flat_samples)

    near_touch_steep = sum(1 for d in steep_samples if d <= 3) / len(steep_samples)
    far_tail_steep = sum(1 for d in steep_samples if d >= 10) / len(steep_samples)
    assert near_touch_steep > 0.60
    assert near_touch_steep > far_tail_steep * 5

    # Higher alpha yields tighter mean distance than lower alpha
    assert (sum(steep_samples) / len(steep_samples)) < (sum(flat_samples) / len(flat_samples))


def test_calibrated_profiles_spread_and_depth_in_range_t2_4() -> None:
    """T2.4, FR-37, FR-52: Three calibrated profiles stay within target spread and depth ranges."""
    results: dict[str, tuple[float, float]] = {}
    for profile_id in ("synthetic_default", "thin_book", "deep_book"):
        profile = get_profile(profile_id)
        book = OrderBook()
        seed_initial_book(book, profile, random.Random(42))  # noqa: S311
        summary = generate_order_flow(book, profile, seed=42, steps=200)
        check_book_invariants(book)

        min_sp, max_sp = profile.target_spread_range
        min_dp, max_dp = profile.target_top_depth_range
        assert (
            min_sp <= summary.avg_spread_ticks <= max_sp
        ), f"{profile_id}: avg_spread={summary.avg_spread_ticks} outside [{min_sp}, {max_sp}]"
        assert (
            min_dp <= summary.avg_top_depth <= max_dp
        ), f"{profile_id}: avg_top_depth={summary.avg_top_depth} outside [{min_dp}, {max_dp}]"
        results[profile_id] = (summary.avg_spread_ticks, summary.avg_top_depth)

    # Ordering sanity: deep_book has more top depth than synthetic_default > thin_book
    assert results["deep_book"][1] > results["synthetic_default"][1] > results["thin_book"][1]
