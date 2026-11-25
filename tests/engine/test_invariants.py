"""Property-based and randomized invariant tests for OrderBook (T1.4).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-11, AC-16, AC-17).
"""

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from opentrade.engine.book import OrderBook, OrderType, Side, STPPolicy
from opentrade.engine.invariants import check_book_invariants
from opentrade.engine.matching import cancel_order, submit_order


@given(seed=st.integers(min_value=0, max_value=10_000))
@settings(max_examples=15, deadline=None)
def test_random_1000_operations_preserve_sorted_sides_and_no_crossed_book(seed: int) -> None:
    """AC-11, AC-17: 1,000 random inserts/cancels maintain sorted sides and no crossed book."""
    rng = random.Random(seed)  # noqa: S311
    book = OrderBook()
    live_ids: list[int] = []
    submitted_qty = 0
    filled_qty = 0
    canceled_qty = 0

    for _ in range(1000):
        action = rng.random()
        if live_ids and action < 0.25:
            oid = rng.choice(live_ids)
            order = book.get_order(oid)
            if order is not None and cancel_order(book, oid):
                canceled_qty += order.remaining_qty
                live_ids.remove(oid)
        else:
            side = Side.BUY if rng.random() < 0.5 else Side.SELL
            otype = rng.choice((OrderType.LIMIT, OrderType.MARKET, OrderType.IOC, OrderType.FOK))
            qty = rng.randint(1, 50)
            price = rng.randint(90, 110) if otype is not OrderType.MARKET else None
            owner = rng.choice(("u1", "u2", None))
            submitted_qty += qty
            res = submit_order(
                book,
                side=side,
                order_type=otype,
                qty=qty,
                price_ticks=price,
                owner_id=owner,
                stp_policy=STPPolicy.CANCEL_NEWEST,
            )
            filled_qty += res.filled_qty
            if res.status in ("RESTING", "PARTIAL") and otype is OrderType.LIMIT:
                if book.get_order(res.order_id) is not None:
                    live_ids.append(res.order_id)
                elif res.remaining_qty > 0:
                    canceled_qty += res.remaining_qty
            else:
                canceled_qty += res.remaining_qty

        check_book_invariants(
            book,
            submitted_qty=submitted_qty,
            total_filled_qty=filled_qty,
            total_canceled_qty=canceled_qty,
        )


def test_identical_seed_produces_identical_event_log_sha256_ac16() -> None:
    """AC-16, FR-15: Same seed and order stream produce identical event log SHA-256."""

    def _run_stream(seed: int) -> str:
        rng = random.Random(seed)  # noqa: S311
        book = OrderBook()
        for _ in range(200):
            side = Side.BUY if rng.random() < 0.5 else Side.SELL
            submit_order(
                book,
                side=side,
                order_type=OrderType.LIMIT,
                qty=rng.randint(1, 25),
                price_ticks=rng.randint(95, 105),
            )
        return book.event_log_sha256()

    assert _run_stream(42) == _run_stream(42)
    assert _run_stream(42) != _run_stream(43)
