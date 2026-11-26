"""Tests for lot sizes, stop orders, iceberg orders, and tagged queue position (T1.5-T1.6).

Follows docs/SRS.md (FR-19, FR-20) and docs/TASKS.md (T1.5, T1.6).
"""

import pytest

from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.matching import cancel_order, submit_order


def test_lot_size_enforcement_fr19() -> None:
    """FR-19, T1.5: Orders must be exact multiples of book.lot_size."""
    book = OrderBook(lot_size=100)
    res = submit_order(book, Side.BUY, OrderType.LIMIT, qty=200, price_ticks=100)
    assert res.status == "RESTING"

    with pytest.raises(ValueError, match="lot_size"):
        submit_order(book, Side.BUY, OrderType.LIMIT, qty=150, price_ticks=100)


def test_iceberg_order_replenishes_at_tail_of_fifo_queue_fr19() -> None:
    """FR-19, T1.5: Iceberg shows display_qty and replenishes hidden_qty at FIFO tail."""
    book = OrderBook()
    ice = submit_order(
        book,
        Side.SELL,
        OrderType.LIMIT,
        qty=250,
        price_ticks=105,
        display_qty=100,
    )
    other = submit_order(book, Side.SELL, OrderType.LIMIT, qty=50, price_ticks=105)

    # Only 100 visible from iceberg + 50 from other = 150 visible at 105
    _, asks = book.depth_snapshot()
    assert asks[0].total_qty == 150
    assert book.queue_position(ice.order_id) == 0
    assert book.queue_position(other.order_id) == 1

    # Buy 100 exhausts iceberg's first visible slice -> replenishes 100 at tail behind `other`
    fill1 = submit_order(book, Side.BUY, OrderType.MARKET, qty=100)
    assert fill1.filled_qty == 100
    assert book.queue_position(other.order_id) == 0
    assert book.queue_position(ice.order_id) == 1

    # Next buy of 50 fills `other`, not the replenished iceberg
    fill2 = submit_order(book, Side.BUY, OrderType.MARKET, qty=50)
    assert fill2.fills[0].maker_order_id == other.order_id


def test_stop_orders_trigger_on_trade_price_fr19() -> None:
    """FR-19, T1.5: Buy stop triggers when trade price >= stop; sell stop when <= stop."""
    book = OrderBook()
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=100, price_ticks=100)
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=100, price_ticks=102)
    submit_order(book, Side.SELL, OrderType.LIMIT, qty=100, price_ticks=105)

    # Buy stop at 102 waits while no trades have occurred at >= 102
    stop_res = submit_order(
        book,
        Side.BUY,
        OrderType.STOP,
        qty=50,
        stop_price_ticks=102,
    )
    assert stop_res.status == "RESTING"
    assert stop_res.filled_qty == 0

    # Trade at 100 does not trigger stop at 102
    submit_order(book, Side.BUY, OrderType.MARKET, qty=100)
    assert book.get_order(stop_res.order_id) is None  # Stop orders sit in stop book
    assert book.best_ask() == 102

    # Trade at 102 triggers the buy stop, which executes 50 against remaining 102 ask
    submit_order(book, Side.BUY, OrderType.MARKET, qty=20)
    _, asks = book.depth_snapshot()
    assert asks[0].price_ticks == 102
    assert asks[0].total_qty == 30  # 100 - 20 (market) - 50 (triggered stop) = 30


def test_stop_order_can_be_canceled_before_trigger_fr19() -> None:
    """FR-19, T1.5: Pending stop order can be canceled before triggering."""
    book = OrderBook()
    stop_res = submit_order(book, Side.SELL, OrderType.STOP, qty=50, stop_price_ticks=95)
    assert cancel_order(book, stop_res.order_id) is True
    assert cancel_order(book, stop_res.order_id) is False


def test_tagged_order_queue_position_tracking_fr20() -> None:
    """FR-20, T1.6: Tagged order tracks orders_ahead and qty_ahead across fills/cancels."""
    book = OrderBook()
    o1 = submit_order(book, Side.BUY, OrderType.LIMIT, qty=100, price_ticks=99, owner_id="mm1")
    o2 = submit_order(book, Side.BUY, OrderType.LIMIT, qty=60, price_ticks=99, owner_id="mm2")
    tagged = submit_order(
        book, Side.BUY, OrderType.LIMIT, qty=40, price_ticks=99, owner_id="user_tag"
    )

    qp = book.tagged_queue_position(tagged.order_id)
    assert qp is not None
    assert qp.orders_ahead == 2
    assert qp.qty_ahead == 160
    assert qp.price_ticks == 99
    assert qp.side is Side.BUY

    # Cancel o1 -> o2 (60) remains ahead
    cancel_order(book, o1.order_id)
    qp2 = book.tagged_queue_position(tagged.order_id)
    assert qp2 is not None
    assert qp2.orders_ahead == 1
    assert qp2.qty_ahead == 60

    # Partial fill of 25 against o2 -> 35 qty remains ahead
    submit_order(book, Side.SELL, OrderType.MARKET, qty=25)
    qp3 = book.tagged_queue_position(tagged.order_id)
    assert qp3 is not None
    assert qp3.orders_ahead == 1
    assert qp3.qty_ahead == 35
    assert o2.order_id != tagged.order_id
