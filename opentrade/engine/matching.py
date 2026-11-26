"""Price-time priority matching, validation, and STP (T1.2-T1.3)."""

from dataclasses import dataclass

from opentrade.engine.book import (
    Fill,
    Order,
    OrderBook,
    OrderType,
    Side,
    StopOrder,
    STPPolicy,
)


@dataclass(frozen=True)
class MatchResult:
    """Result of submitting or modifying an order on the OrderBook."""

    order_id: int
    status: str
    filled_qty: int
    remaining_qty: int
    fills: tuple[Fill, ...]


def _is_strict_int(value: object) -> bool:
    """Return True only for non-boolean integers."""
    return isinstance(value, int) and not isinstance(value, bool)


def validate_order_inputs(
    side: Side | str,
    order_type: OrderType | str,
    qty: int,
    price_ticks: int | None,
    lot_size: int = 1,
    stop_price_ticks: int | None = None,
    display_qty: int | None = None,
) -> tuple[Side, OrderType, int, int]:
    """Validate order inputs and normalize enums; raises ValueError on invalid input."""
    try:
        parsed_side = side if isinstance(side, Side) else Side(str(side).upper())
        parsed_type = (
            order_type if isinstance(order_type, OrderType) else OrderType(str(order_type).upper())
        )
    except ValueError as exc:
        raise ValueError(f"Invalid side or order_type: {side!r}, {order_type!r}") from exc

    if not _is_strict_int(qty) or qty <= 0:
        raise ValueError(f"qty must be a positive integer, got {qty!r}")
    if qty % lot_size != 0:
        raise ValueError(f"qty={qty} must be an exact multiple of lot_size={lot_size}")
    if display_qty is not None and (not _is_strict_int(display_qty) or display_qty <= 0):
        raise ValueError(f"display_qty must be a positive integer, got {display_qty!r}")

    if parsed_type is OrderType.STOP:
        if (
            stop_price_ticks is None
            or not _is_strict_int(stop_price_ticks)
            or stop_price_ticks <= 0
        ):
            raise ValueError(f"stop_price_ticks must be positive, got {stop_price_ticks!r}")
        return parsed_side, parsed_type, qty, stop_price_ticks

    if parsed_type is OrderType.MARKET:
        resolved_price = 0 if price_ticks is None else price_ticks
        if not _is_strict_int(resolved_price) or resolved_price < 0:
            raise ValueError(f"Invalid market price_ticks: {price_ticks!r}")
        return parsed_side, parsed_type, qty, resolved_price

    if price_ticks is None or not _is_strict_int(price_ticks) or price_ticks <= 0:
        raise ValueError(f"price_ticks must be a positive integer, got {price_ticks!r}")
    return parsed_side, parsed_type, qty, price_ticks


def _can_cross(
    incoming_side: Side, incoming_type: OrderType, price_ticks: int, opp_price: int
) -> bool:
    """Return True if an incoming order can trade against opp_price."""
    if incoming_type is OrderType.MARKET:
        return True
    if incoming_side is Side.BUY:
        return price_ticks >= opp_price
    return price_ticks <= opp_price


def _fok_available_qty(
    book: OrderBook,
    side: Side,
    price_ticks: int,
    owner_id: str | None,
    stp_policy: STPPolicy,
) -> int:
    """Compute fillable opposing liquidity for an FOK order without mutating the book."""
    opp_prices, opp_levels = book.opposing_prices_and_queues(side)
    total = 0
    for opp_price in reversed(opp_prices):
        if not _can_cross(side, OrderType.FOK, price_ticks, opp_price):
            break
        for resting in opp_levels[opp_price]:
            if owner_id is not None and resting.owner_id == owner_id:
                if stp_policy is STPPolicy.CANCEL_NEWEST:
                    return total
                if stp_policy is STPPolicy.CANCEL_OLDEST:
                    continue
            total += resting.remaining_qty
    return total


def submit_order(
    book: OrderBook,
    side: Side | str,
    order_type: OrderType | str,
    qty: int,
    price_ticks: int | None = None,
    owner_id: str | None = None,
    stp_policy: STPPolicy = STPPolicy.CANCEL_NEWEST,
    display_qty: int | None = None,
    stop_price_ticks: int | None = None,
) -> MatchResult:
    """Validate and submit an order to the book with price-time priority matching."""
    parsed_side, parsed_type, clean_qty, clean_price = validate_order_inputs(
        side,
        order_type,
        qty,
        price_ticks,
        lot_size=book.lot_size,
        stop_price_ticks=stop_price_ticks,
        display_qty=display_qty,
    )
    order_id = book.next_order_id()
    seq = book.next_seq()
    book.record_event(
        ("SUBMIT", seq, order_id, parsed_side.value, parsed_type.value, clean_qty, clean_price)
    )

    if parsed_type is OrderType.STOP:
        book.add_stop_order(
            StopOrder(
                order_id=order_id,
                side=parsed_side,
                stop_price_ticks=clean_price,
                qty=clean_qty,
                owner_id=owner_id,
                timestamp_seq=seq,
            )
        )
        return MatchResult(order_id, "RESTING", 0, clean_qty, ())

    opp_prices, opp_levels = book.opposing_prices_and_queues(parsed_side)
    opp_side = Side.SELL if parsed_side is Side.BUY else Side.BUY

    if (
        parsed_type is OrderType.POST_ONLY
        and opp_prices
        and _can_cross(parsed_side, OrderType.LIMIT, clean_price, opp_prices[-1])
    ):
        book.record_event(("CANCEL", book.next_seq(), order_id, clean_qty, "POST_ONLY"))
        return MatchResult(order_id, "CANCELED", 0, clean_qty, ())

    if parsed_type is OrderType.FOK:
        avail = _fok_available_qty(book, parsed_side, clean_price, owner_id, stp_policy)
        if avail < clean_qty:
            book.record_event(("CANCEL", book.next_seq(), order_id, clean_qty, "FOK"))
            return MatchResult(order_id, "CANCELED", 0, clean_qty, ())

    remaining = clean_qty
    fills: list[Fill] = []
    stp_canceled = False

    while remaining > 0 and opp_prices:
        best_opp = opp_prices[-1]
        if not _can_cross(parsed_side, parsed_type, clean_price, best_opp):
            break
        queue = opp_levels[best_opp]
        resting = queue[0]

        if (
            owner_id is not None
            and resting.owner_id == owner_id
            and stp_policy is not STPPolicy.NONE
        ):
            if stp_policy is STPPolicy.CANCEL_NEWEST:
                stp_canceled = True
                book.record_event(("STP_CANCEL_NEWEST", book.next_seq(), order_id, remaining))
                break
            canceled_old = book.pop_filled_head(opp_side, best_opp)
            book.record_event(
                (
                    "STP_CANCEL_OLDEST",
                    book.next_seq(),
                    canceled_old.order_id,
                    canceled_old.remaining_qty,
                )
            )
            continue

        trade_qty = min(remaining, resting.remaining_qty)
        trade_seq = book.next_seq()
        fill = Fill(
            maker_order_id=resting.order_id,
            taker_order_id=order_id,
            price_ticks=best_opp,
            qty=trade_qty,
            taker_side=parsed_side,
            seq=trade_seq,
        )
        fills.append(fill)
        book.last_trade_price_ticks = best_opp
        book.record_event(("FILL", trade_seq, resting.order_id, order_id, best_opp, trade_qty))

        remaining -= trade_qty
        resting.remaining_qty -= trade_qty
        if resting.remaining_qty == 0:
            book.pop_filled_head(opp_side, best_opp)

    if fills and book.last_trade_price_ticks is not None:
        for triggered in book.pop_triggered_stops(book.last_trade_price_ticks):
            submit_order(
                book,
                side=triggered.side,
                order_type=OrderType.MARKET,
                qty=triggered.qty,
                owner_id=triggered.owner_id,
                stp_policy=stp_policy,
            )

    filled_qty = clean_qty - remaining
    if remaining > 0 and not stp_canceled and parsed_type in (OrderType.LIMIT, OrderType.POST_ONLY):
        visible_qty = min(remaining, display_qty) if display_qty is not None else remaining
        hidden_qty = remaining - visible_qty
        resting_order = Order(
            order_id=order_id,
            side=parsed_side,
            price_ticks=clean_price,
            qty=clean_qty,
            remaining_qty=visible_qty,
            owner_id=owner_id,
            timestamp_seq=seq,
            order_type=parsed_type,
            display_qty=display_qty,
            hidden_qty=hidden_qty,
        )
        book.add_resting_order(resting_order)
        status = "PARTIAL" if filled_qty > 0 else "RESTING"
        return MatchResult(order_id, status, filled_qty, remaining, tuple(fills))

    if remaining > 0:
        book.record_event(("CANCEL", book.next_seq(), order_id, remaining, parsed_type.value))
        status = "PARTIAL" if filled_qty > 0 else "CANCELED"
        return MatchResult(order_id, status, filled_qty, remaining, tuple(fills))

    return MatchResult(order_id, "FILLED", filled_qty, 0, tuple(fills))


def cancel_order(book: OrderBook, order_id: int) -> bool:
    """Cancel a resting or pending stop order by ID; returns True if canceled."""
    removed = book.cancel_resting_order(order_id)
    if removed is not None:
        book.record_event(("CANCEL", book.next_seq(), order_id, removed.remaining_qty, "USER"))
        return True
    removed_stop = book.cancel_stop_order(order_id)
    if removed_stop is not None:
        book.record_event(("CANCEL", book.next_seq(), order_id, removed_stop.qty, "STOP"))
        return True
    return False


def modify_order(
    book: OrderBook,
    order_id: int,
    new_qty: int | None = None,
    new_price_ticks: int | None = None,
    stp_policy: STPPolicy = STPPolicy.CANCEL_NEWEST,
) -> MatchResult | None:
    """Modify a resting order; size decrease keeps FIFO priority, else cancel-and-replace."""
    existing = book.get_order(order_id)
    if existing is None:
        return None

    target_qty = existing.remaining_qty if new_qty is None else new_qty
    target_price = existing.price_ticks if new_price_ticks is None else new_price_ticks
    if not _is_strict_int(target_qty) or target_qty <= 0:
        raise ValueError(f"new_qty must be a positive integer, got {target_qty!r}")
    if not _is_strict_int(target_price) or target_price <= 0:
        raise ValueError(f"new_price_ticks must be a positive integer, got {target_price!r}")

    if target_price == existing.price_ticks and target_qty <= existing.remaining_qty:
        delta = existing.remaining_qty - target_qty
        existing.remaining_qty = target_qty
        if delta > 0:
            book.record_event(("MODIFY_DOWN", book.next_seq(), order_id, delta))
        return MatchResult(order_id, "RESTING", 0, target_qty, ())

    cancel_order(book, order_id)
    return submit_order(
        book,
        side=existing.side,
        order_type=existing.order_type,
        qty=target_qty,
        price_ticks=target_price,
        owner_id=existing.owner_id,
        stp_policy=stp_policy,
    )
