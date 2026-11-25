"""Tests for deterministic synthetic order-flow generator (T1.5).

Follows docs/SRS.md (FR-15, FR-16, FR-17, FR-21) and docs/ACCEPTANCE_CRITERIA.md (AC-16, AC-17).
"""

import random

from opentrade.engine.book import OrderBook
from opentrade.engine.invariants import check_book_invariants
from opentrade.engine.order_flow import generate_order_flow, seed_initial_book
from opentrade.engine.profiles import EngineProvenance, get_profile


def test_order_flow_determinism_and_no_global_random_state() -> None:
    """AC-16, FR-15, FR-16: Identical seed produces identical flow and event_log_sha256."""
    profile = get_profile("synthetic_default")

    # Pollute global random state to prove engine ignores it
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
    assert s1.limit_count > 0
    assert s1.market_count > 0
    check_book_invariants(b1)

    b3 = OrderBook()
    seed_initial_book(b3, profile, random.Random(43))  # noqa: S311
    s3 = generate_order_flow(b3, profile, seed=43, steps=150)
    assert s3.event_log_sha256 != s1.event_log_sha256


def test_hawkes_regime_and_thin_book_preserve_invariants() -> None:
    """AC-17, FR-21: Hawkes excitation and thin_book regime maintain book invariants."""
    for profile_id in ("thin_book", "deep_book", "high_volatility"):
        profile = get_profile(profile_id)
        book = OrderBook()
        seed_initial_book(book, profile, random.Random(7))  # noqa: S311
        summary = generate_order_flow(book, profile, seed=7, steps=200)
        assert summary.steps == 200
        check_book_invariants(book)
