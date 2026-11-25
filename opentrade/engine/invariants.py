"""Order book invariant verification helpers (T1.4, AC-11, AC-17)."""

from opentrade.engine.book import OrderBook, Side


def check_book_invariants(
    book: OrderBook,
    submitted_qty: int | None = None,
    total_filled_qty: int | None = None,
    total_canceled_qty: int | None = None,
) -> None:
    """Assert structural, sorting, FIFO, and volume-conservation invariants on OrderBook."""
    if book.is_crossed():
        raise AssertionError(
            f"Crossed book invariant violated: {book.best_bid()} >= {book.best_ask()}"
        )

    bid_prices, bid_levels = book.raw_levels(Side.BUY)
    ask_prices, ask_levels = book.raw_levels(Side.SELL)

    # Bids stored ascending (best at [-1]); asks stored descending (best at [-1])
    if bid_prices != sorted(bid_prices) or len(bid_prices) != len(set(bid_prices)):
        raise AssertionError(f"Bid prices not strictly ascending: {bid_prices}")
    if ask_prices != sorted(ask_prices, reverse=True) or len(ask_prices) != len(set(ask_prices)):
        raise AssertionError(f"Ask prices not strictly descending: {ask_prices}")
    if set(bid_prices) != set(bid_levels.keys()):
        raise AssertionError("Bid price list out of sync with level map")
    if set(ask_prices) != set(ask_levels.keys()):
        raise AssertionError("Ask price list out of sync with level map")

    seen_ids: set[int] = set()
    for side, levels in ((Side.BUY, bid_levels), (Side.SELL, ask_levels)):
        for price, queue in levels.items():
            if not queue:
                raise AssertionError(f"Empty queue left at {side.value} level {price}")
            prev_seq = -1
            for order in queue:
                if order.side is not side or order.price_ticks != price:
                    raise AssertionError(f"Order {order.order_id} misplaced at {side} {price}")
                if order.remaining_qty <= 0 or order.remaining_qty > order.qty:
                    raise AssertionError(f"Invalid remaining_qty on order {order.order_id}")
                if order.timestamp_seq < prev_seq:
                    raise AssertionError(f"FIFO order violated at {side} {price}")
                prev_seq = order.timestamp_seq
                if book.get_order(order.order_id) is not order:
                    raise AssertionError(f"Order index mismatch for {order.order_id}")
                seen_ids.add(order.order_id)

    if (
        submitted_qty is not None
        and total_filled_qty is not None
        and total_canceled_qty is not None
    ):
        resting_qty = book.total_resting_qty()
        expected = resting_qty + 2 * total_filled_qty + total_canceled_qty
        if submitted_qty != expected:
            raise AssertionError(
                f"Volume conservation violated: submitted={submitted_qty} != "
                f"resting={resting_qty} + 2*filled={total_filled_qty} "
                f"+ canceled={total_canceled_qty}"
            )
