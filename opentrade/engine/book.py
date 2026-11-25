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

    def __init__(self) -> None:
        """Initialize an empty order book with deterministic sequence counters."""
        self._bids: dict[int, deque[Order]] = {}
        self._asks: dict[int, deque[Order]] = {}
        self._bid_prices: list[int] = []  # Sorted ascending; best bid is [-1]
        self._ask_prices: list[int] = []  # Sorted descending; best ask is [-1]
        self._orders: dict[int, Order] = {}
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
        """Pop and unregister the head order at a price level."""
        levels = self._bids if side is Side.BUY else self._asks
        order = levels[price_ticks].popleft()
        self._orders.pop(order.order_id, None)
        if not levels[price_ticks]:
            self.remove_empty_level(side, price_ticks)
        return order

    def queue_position(self, order_id: int) -> int | None:
        """Return 0-indexed FIFO queue position at the order's price level, or None."""
        order = self._orders.get(order_id)
        if order is None:
            return None
        levels = self._bids if order.side is Side.BUY else self._asks
        for idx, candidate in enumerate(levels[order.price_ticks]):
            if candidate.order_id == order_id:
                return idx
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
