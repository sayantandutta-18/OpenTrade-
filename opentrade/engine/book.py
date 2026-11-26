"""Limit order book structure with FIFO price levels and integer ticks (T1.1)."""

import bisect
import hashlib
import json
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Side(StrEnum):
    """Order side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Supported order types."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "POST_ONLY"
    STOP = "STOP"


class STPPolicy(StrEnum):
    """Self-trade prevention policy."""

    CANCEL_NEWEST = "CANCEL_NEWEST"
    CANCEL_OLDEST = "CANCEL_OLDEST"
    NONE = "NONE"


@dataclass
class Order:
    """Resting or incoming order represented in integer ticks."""

    order_id: int
    side: Side
    price_ticks: int
    qty: int
    remaining_qty: int
    owner_id: str | None = None
    timestamp_seq: int = 0
    order_type: OrderType = OrderType.LIMIT
    display_qty: int | None = None
    hidden_qty: int = 0


@dataclass(frozen=True)
class StopOrder:
    """Pending stop-market order waiting for trade trigger."""

    order_id: int
    side: Side
    stop_price_ticks: int
    qty: int
    owner_id: str | None = None
    timestamp_seq: int = 0


@dataclass(frozen=True)
class QueuePosition:
    """Queue position snapshot for a resting order."""

    orders_ahead: int
    qty_ahead: int
    price_ticks: int
    side: Side


@dataclass(frozen=True)
class Fill:
    """Immutable trade fill emitted by price-time priority matching."""

    maker_order_id: int
    taker_order_id: int
    price_ticks: int
    qty: int
    taker_side: Side
    seq: int


@dataclass(frozen=True)
class DepthLevel:
    """Aggregated liquidity at a single integer tick price level."""

    price_ticks: int
    total_qty: int
    order_count: int


class OrderBook:
    """Price-time priority limit order book using FIFO deques and integer ticks."""

    def __init__(self, lot_size: int = 1) -> None:
        """Initialize an empty order book with deterministic sequence counters."""
        if isinstance(lot_size, bool) or not isinstance(lot_size, int) or lot_size <= 0:
            raise ValueError(f"lot_size must be a positive integer, got {lot_size!r}")
        self.lot_size: int = lot_size
        self._bids: dict[int, deque[Order]] = {}
        self._asks: dict[int, deque[Order]] = {}
        self._bid_prices: list[int] = []  # Sorted ascending; best bid is [-1]
        self._ask_prices: list[int] = []  # Sorted descending; best ask is [-1]
        self._orders: dict[int, Order] = {}
        self._stop_orders: list[StopOrder] = []
        self.last_trade_price_ticks: int | None = None
        self._next_id: int = 1
        self._seq: int = 0
        self.event_log: list[tuple[Any, ...]] = []

    def next_order_id(self) -> int:
        """Allocate and return the next sequential order ID."""
        oid = self._next_id
        self._next_id += 1
        return oid

    def next_seq(self) -> int:
        """Advance and return the deterministic event sequence counter."""
        self._seq += 1
        return self._seq

    def record_event(self, event: tuple[Any, ...]) -> None:
        """Append a deterministic event tuple to the event log."""
        self.event_log.append(event)

    def event_log_sha256(self) -> str:
        """Return SHA-256 hex digest of the canonical event log."""
        payload = json.dumps(self.event_log, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def best_bid(self) -> int | None:
        """Return highest resting bid price in ticks, or None if no bids."""
        return self._bid_prices[-1] if self._bid_prices else None

    def best_ask(self) -> int | None:
        """Return lowest resting ask price in ticks, or None if no asks."""
        return self._ask_prices[-1] if self._ask_prices else None

    def spread_ticks(self) -> int | None:
        """Return best_ask - best_bid in integer ticks, or None if one side is empty."""
        bid, ask = self.best_bid(), self.best_ask()
        if bid is None or ask is None:
            return None
        return ask - bid

    def mid_price_ticks(self) -> float | None:
        """Return midpoint in ticks as a float for reporting, or None if empty."""
        bid, ask = self.best_bid(), self.best_ask()
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2.0

    def is_crossed(self) -> bool:
        """Return True if best_bid >= best_ask."""
        bid, ask = self.best_bid(), self.best_ask()
        return bid is not None and ask is not None and bid >= ask

    def get_order(self, order_id: int) -> Order | None:
        """Return resting Order by ID in O(1), or None if absent."""
        return self._orders.get(order_id)

    def total_resting_qty(self, side: Side | None = None) -> int:
        """Return total resting quantity across one or both sides."""
        if side is None:
            return sum(o.remaining_qty for o in self._orders.values())
        return sum(o.remaining_qty for o in self._orders.values() if o.side is side)

    def resting_order_ids(self) -> list[int]:
        """Return all currently resting order IDs in insertion/dict order."""
        return list(self._orders.keys())

    def top_of_book_depth(self) -> int:
        """Return combined visible quantity at best bid and best ask."""
        total = 0
        bid = self.best_bid()
        ask = self.best_ask()
        if bid is not None:
            total += sum(o.remaining_qty for o in self._bids[bid])
        if ask is not None:
            total += sum(o.remaining_qty for o in self._asks[ask])
        return total

    def add_resting_order(self, order: Order) -> None:
        """Insert a resting order at the tail of its price level FIFO queue."""
        levels = self._bids if order.side is Side.BUY else self._asks
        if order.price_ticks not in levels:
            levels[order.price_ticks] = deque()
            if order.side is Side.BUY:
                bisect.insort(self._bid_prices, order.price_ticks)
            else:
                # Keep _ask_prices sorted descending so [-1] is lowest ask
                idx = bisect.bisect_left([-p for p in self._ask_prices], -order.price_ticks)
                self._ask_prices.insert(idx, order.price_ticks)
        levels[order.price_ticks].append(order)
        self._orders[order.order_id] = order

    def remove_empty_level(self, side: Side, price_ticks: int) -> None:
        """Remove an empty price level from both dict and sorted price list."""
        levels = self._bids if side is Side.BUY else self._asks
        queue = levels.get(price_ticks)
        if queue is not None and not queue:
            del levels[price_ticks]
            if side is Side.BUY:
                idx = bisect.bisect_left(self._bid_prices, price_ticks)
                if idx < len(self._bid_prices) and self._bid_prices[idx] == price_ticks:
                    self._bid_prices.pop(idx)
            else:
                idx = bisect.bisect_left([-p for p in self._ask_prices], -price_ticks)
                if idx < len(self._ask_prices) and self._ask_prices[idx] == price_ticks:
                    self._ask_prices.pop(idx)

    def cancel_resting_order(self, order_id: int) -> Order | None:
        """Remove and return a resting order by ID, cleaning up empty levels."""
        order = self._orders.pop(order_id, None)
        if order is None:
            return None
        levels = self._bids if order.side is Side.BUY else self._asks
        queue = levels[order.price_ticks]
        queue.remove(order)
        if not queue:
            self.remove_empty_level(order.side, order.price_ticks)
        return order

    def opposing_prices_and_queues(
        self, incoming_side: Side
    ) -> tuple[list[int], dict[int, deque[Order]]]:
        """Return reference to opposing sorted price list (best at [-1]) and level dict."""
        if incoming_side is Side.BUY:
            return self._ask_prices, self._asks
        return self._bid_prices, self._bids

    def pop_filled_head(self, side: Side, price_ticks: int) -> Order:
        """Pop the head order at a price level, replenishing iceberg reserve if present."""
        levels = self._bids if side is Side.BUY else self._asks
        order = levels[price_ticks].popleft()
        if order.hidden_qty > 0 and order.display_qty:
            replenish = min(order.hidden_qty, order.display_qty)
            order.remaining_qty = replenish
            order.hidden_qty -= replenish
            order.timestamp_seq = self.next_seq()
            levels[price_ticks].append(order)
            self.record_event(("ICEBERG_REPLENISH", order.timestamp_seq, order.order_id, replenish))
            return order
        self._orders.pop(order.order_id, None)
        if not levels[price_ticks]:
            self.remove_empty_level(side, price_ticks)
        return order

    def add_stop_order(self, stop_order: StopOrder) -> None:
        """Register a pending stop order."""
        self._stop_orders.append(stop_order)

    def cancel_stop_order(self, order_id: int) -> StopOrder | None:
        """Cancel and return a pending stop order by ID, or None if absent."""
        for idx, stop_order in enumerate(self._stop_orders):
            if stop_order.order_id == order_id:
                return self._stop_orders.pop(idx)
        return None

    def pop_triggered_stops(self, trade_price_ticks: int) -> list[StopOrder]:
        """Remove and return stop orders triggered by trade_price_ticks in FIFO order."""
        triggered: list[StopOrder] = []
        remaining: list[StopOrder] = []
        for stop_order in self._stop_orders:
            is_buy_hit = (
                stop_order.side is Side.BUY and trade_price_ticks >= stop_order.stop_price_ticks
            )
            is_sell_hit = (
                stop_order.side is Side.SELL and trade_price_ticks <= stop_order.stop_price_ticks
            )
            if is_buy_hit or is_sell_hit:
                triggered.append(stop_order)
            else:
                remaining.append(stop_order)
        self._stop_orders = remaining
        return triggered

    def queue_position(self, order_id: int) -> int | None:
        """Return 0-indexed FIFO queue position at the order's price level, or None."""
        qp = self.tagged_queue_position(order_id)
        return qp.orders_ahead if qp is not None else None

    def tagged_queue_position(self, order_id: int) -> QueuePosition | None:
        """Return QueuePosition (orders_ahead, qty_ahead, price_ticks, side) for a resting order."""
        order = self._orders.get(order_id)
        if order is None:
            return None
        levels = self._bids if order.side is Side.BUY else self._asks
        qty_ahead = 0
        for idx, candidate in enumerate(levels[order.price_ticks]):
            if candidate.order_id == order_id:
                return QueuePosition(idx, qty_ahead, order.price_ticks, order.side)
            qty_ahead += candidate.remaining_qty
        return None

    def depth_snapshot(self, levels: int = 10) -> tuple[list[DepthLevel], list[DepthLevel]]:
        """Return (bids_desc, asks_asc) aggregated depth levels up to `levels` per side."""
        bids: list[DepthLevel] = []
        for price in reversed(self._bid_prices[-levels:]):
            q = self._bids[price]
            bids.append(DepthLevel(price, sum(o.remaining_qty for o in q), len(q)))
        asks: list[DepthLevel] = []
        for price in reversed(self._ask_prices[-levels:]):
            q = self._asks[price]
            asks.append(DepthLevel(price, sum(o.remaining_qty for o in q), len(q)))
        return bids, asks

    def raw_levels(self, side: Side) -> tuple[list[int], dict[int, deque[Order]]]:
        """Return (sorted_prices_best_last, price_to_deque) for invariant verification."""
        if side is Side.BUY:
            return self._bid_prices, self._bids
        return self._ask_prices, self._asks
