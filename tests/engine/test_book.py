"""Tests for order book structure, matching, validation, and STP (T1.1-T1.3).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-11 through AC-17) and docs/TRD.md.
"""

import pytest

from opentrade.engine.book import OrderBook, OrderType, Side, STPPolicy
from opentrade.engine.matching import cancel_order, modify_order, submit_order


def test_book_sorted_sides_and_depth_snapshot_t1_1() -> None:
    """AC-11, FR-11, FR-12: Bids sorted high-to-low, asks low-to-high, integer ticks."""
    book = OrderBook()
    submit_order(book, Side.BUY, OrderType.LIMIT, qty=100, price_ticks=99)
    submit_order(book, Side.BUY, OrderType.LIMIT, qty=200, price_ticks=100)
    submit_order(book, Side.BUY, OrderType.LIMIT, qty=50, price_ticks=98)
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=120, price_ticks=103)
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=80, price_ticks=101)
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=60, price_ticks=102)

    assert book.best_bid() == 100
    assert book.best_ask() == 101
    assert book.spread_ticks() == 1
    assert book.mid_price_ticks() == 100.5

    bids, asks = book.depth_snapshot(levels=10)
    assert [lvl.price_ticks for lvl in bids] == [100, 99, 98]
    assert [lvl.price_ticks for lvl in asks] == [101, 102, 103]


def test_market_buy_walks_asks_in_price_order_ac12() -> None:
    """AC-12, FR-14: Asks 101(100), 102(200), bid 99(150); market buy 150 fills 100@101 + 50@102."""
    book = OrderBook()
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=100, price_ticks=101)
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=200, price_ticks=102)
    submit_order(book, Side.BUY, OrderType.LIMIT, qty=150, price_ticks=99)

    res = submit_order(book, Side.BUY, OrderType.MARKET, qty=150)
    assert res.status == "FILLED"
    assert res.filled_qty == 150
    assert res.remaining_qty == 0
    assert [(f.price_ticks, f.qty) for f in res.fills] == [(101, 100), (102, 50)]
    assert book.best_ask() == 102
    assert book.depth_snapshot()[1][0].total_qty == 150


def test_fifo_priority_at_same_price_level_ac13() -> None:
    """AC-13, FR-11, FR-14: Two resting orders at same price fill in arrival order (FIFO)."""
    book = OrderBook()
    o1 = submit_order(book, Side.SELL, OrderType.LIMIT, qty=50, price_ticks=105)
    o2 = submit_order(book, Side.SELL, OrderType.LIMIT, qty=50, price_ticks=105)

    assert book.queue_position(o1.order_id) == 0
    assert book.queue_position(o2.order_id) == 1

    res = submit_order(book, Side.BUY, OrderType.LIMIT, qty=60, price_ticks=105)
    assert res.filled_qty == 60
    assert [(f.maker_order_id, f.qty) for f in res.fills] == [
        (o1.order_id, 50),
        (o2.order_id, 10),
    ]
    assert book.get_order(o1.order_id) is None
    rem_o2 = book.get_order(o2.order_id)
    assert rem_o2 is not None and rem_o2.remaining_qty == 40


def test_fok_insufficient_liquidity_leaves_book_unchanged_ac14() -> None:
    """AC-14, FR-13: FOK order that cannot fill completely returns 0 fills and no book change."""
    book = OrderBook()
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=100, price_ticks=101)
    before_hash = book.event_log_sha256()

    res = submit_order(book, Side.BUY, OrderType.FOK, qty=150, price_ticks=101)
    assert res.status == "CANCELED"
    assert res.filled_qty == 0
    assert res.fills == ()
    assert book.best_ask() == 101
    assert book.depth_snapshot()[1][0].total_qty == 100
    assert book.event_log_sha256() != before_hash  # FOK cancellation logged deterministically


def test_ioc_fills_partial_and_never_rests_ac15() -> None:
    """AC-15, FR-13: IOC fills available liquidity and cancels unfilled remainder."""
    book = OrderBook()
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=40, price_ticks=100)

    res = submit_order(book, Side.BUY, OrderType.IOC, qty=100, price_ticks=100)
    assert res.status == "PARTIAL"
    assert res.filled_qty == 40
    assert res.remaining_qty == 60
    assert book.best_bid() is None
    assert book.best_ask() is None


def test_post_only_rejects_crossing_and_rests_passive() -> None:
    """FR-13: Post-only rejects/cancels if it would cross best opposite price."""
    book = OrderBook()
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=50, price_ticks=100)

    crossed = submit_order(book, Side.BUY, OrderType.POST_ONLY, qty=20, price_ticks=100)
    assert crossed.status == "CANCELED"
    assert crossed.filled_qty == 0
    assert book.best_bid() is None

    passive = submit_order(book, Side.BUY, OrderType.POST_ONLY, qty=20, price_ticks=99)
    assert passive.status == "RESTING"
    assert book.best_bid() == 99


def test_cancel_and_modify_priority_rules() -> None:
    """FR-13: Cancel removes order; size decrease keeps FIFO, size increase/reprice loses FIFO."""
    book = OrderBook()
    o1 = submit_order(book, Side.BUY, OrderType.LIMIT, qty=100, price_ticks=100)
    o2 = submit_order(book, Side.BUY, OrderType.LIMIT, qty=100, price_ticks=100)

    # Size decrease at same price preserves queue position 0
    mod_down = modify_order(book, o1.order_id, new_qty=60)
    assert mod_down is not None
    assert book.queue_position(o1.order_id) == 0

    # Size increase at same price moves o1 behind o2
    mod_up = modify_order(book, o1.order_id, new_qty=120)
    assert mod_up is not None
    assert book.queue_position(o2.order_id) == 0
    assert book.queue_position(mod_up.order_id) == 1

    assert cancel_order(book, o2.order_id) is True
    assert cancel_order(book, o2.order_id) is False


def test_order_validation_and_self_trade_prevention_t1_3() -> None:
    """FR-12, FR-19: Strict input validation and STP (CANCEL_NEWEST / CANCEL_OLDEST)."""
    book = OrderBook()
    with pytest.raises(ValueError):
        submit_order(book, Side.BUY, OrderType.LIMIT, qty=0, price_ticks=100)
    with pytest.raises(ValueError):
        submit_order(book, Side.BUY, OrderType.LIMIT, qty=10, price_ticks=0)
    with pytest.raises(ValueError):
        submit_order(book, Side.BUY, OrderType.LIMIT, qty=True, price_ticks=100)

    # STP CANCEL_NEWEST
    r1 = submit_order(book, Side.SELL, OrderType.LIMIT, qty=50, price_ticks=100, owner_id="alice")
    stp_new = submit_order(
        book,
        Side.BUY,
        OrderType.LIMIT,
        qty=50,
        price_ticks=100,
        owner_id="alice",
        stp_policy=STPPolicy.CANCEL_NEWEST,
    )
    assert stp_new.filled_qty == 0
    assert stp_new.status == "CANCELED"
    assert book.get_order(r1.order_id) is not None

    # STP CANCEL_OLDEST cancels alice's resting order and rests/fills incoming
    stp_old = submit_order(
        book,
        Side.BUY,
        OrderType.LIMIT,
        qty=50,
        price_ticks=100,
        owner_id="alice",
        stp_policy=STPPolicy.CANCEL_OLDEST,
    )
    assert stp_old.filled_qty == 0
    assert book.get_order(r1.order_id) is None
    assert book.best_bid() == 100
