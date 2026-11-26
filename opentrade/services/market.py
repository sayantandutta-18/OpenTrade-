"""Market quotes, price history, and per-user watchlist services (T7.2)."""

import hashlib
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from opentrade.adapters.market_twelvedata import AdapterError, HistoryBar, QuoteData
from opentrade.storage.db import get_connection
from opentrade.storage.watchlist_repo import WatchlistRepository


class MarketDataAdapter(Protocol):
    """Protocol for market data providers."""

    def fetch_quote(self, symbol: str) -> QuoteData: ...

    def fetch_history(self, symbol: str, days: int = 60) -> list[HistoryBar]: ...


def _symbol_seed(symbol: str) -> int:
    """Derive a deterministic integer seed from a ticker symbol."""
    digest = hashlib.sha256(symbol.strip().upper().encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


def _simulated_quote(symbol: str, reason: str) -> dict[str, Any]:
    """Generate deterministic simulated quote labeled SIMULATED (never REAL, AC-28)."""
    clean = symbol.strip().upper()
    rng = random.Random(_symbol_seed(clean))  # noqa: S311
    base = round(50.0 + rng.random() * 250.0, 2)
    chg = round((rng.random() - 0.5) * 4.0, 2)
    prev = round(base - chg, 2)
    pct = round((chg / prev) * 100.0, 2) if prev > 0 else 0.0
    return {
        "symbol": clean,
        "price": base,
        "change": chg,
        "change_pct": pct,
        "open": prev,
        "prev_close": prev,
        "high": round(max(base, prev) + 1.1, 2),
        "low": round(min(base, prev) - 1.1, 2),
        "label": "SIMULATED",
        "source": "simulated_fallback",
        "reason": reason,
        "as_of": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _simulated_history(symbol: str, days: int, reason: str) -> dict[str, Any]:
    """Generate deterministic simulated daily OHLCV bars labeled SIMULATED."""
    clean = symbol.strip().upper()
    rng = random.Random(_symbol_seed(clean))  # noqa: S311
    price = 80.0 + rng.random() * 150.0
    start = datetime(2026, 1, 15, tzinfo=UTC) - timedelta(days=days)
    points: list[dict[str, Any]] = []
    for i in range(days):
        dt = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        ret = (rng.random() - 0.49) * 0.03
        open_px = round(price, 2)
        close_px = round(max(1.0, price * (1.0 + ret)), 2)
        high_px = round(max(open_px, close_px) * 1.01, 2)
        low_px = round(min(open_px, close_px) * 0.99, 2)
        points.append(
            {
                "date": dt,
                "open": open_px,
                "high": high_px,
                "low": low_px,
                "close": close_px,
                "volume": int(500_000 + rng.random() * 1_500_000),
            }
        )
        price = close_px
    return {
        "symbol": clean,
        "points": points,
        "label": "SIMULATED",
        "source": "simulated_fallback",
        "reason": reason,
    }


def get_quote(symbol: str, adapter: MarketDataAdapter | None = None) -> dict[str, Any]:
    """Fetch market quote with REAL label on live success, else SIMULATED fallback (AC-28)."""
    clean = symbol.strip().upper()
    if adapter is None:
        return _simulated_quote(clean, reason="Live market provider not configured")
    try:
        q = adapter.fetch_quote(clean)
        return {
            "symbol": q.symbol,
            "price": q.price,
            "change": q.change,
            "change_pct": q.change_pct,
            "open": q.open,
            "prev_close": q.prev_close,
            "high": q.high,
            "low": q.low,
            "label": "REAL",
            "source": q.source,
            "as_of": q.as_of,
        }
    except (AdapterError, ValueError, OSError) as exc:
        return _simulated_quote(clean, reason=str(exc))


def get_history(
    symbol: str,
    days: int = 60,
    adapter: MarketDataAdapter | None = None,
) -> dict[str, Any]:
    """Fetch daily OHLCV history with REAL label on live success, else SIMULATED fallback."""
    clean = symbol.strip().upper()
    if adapter is None:
        return _simulated_history(clean, days, reason="Live market provider not configured")
    try:
        bars = adapter.fetch_history(clean, days=days)
        return {
            "symbol": clean,
            "points": [
                {
                    "date": b.date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars
            ],
            "label": "REAL",
            "source": "twelvedata",
        }
    except (AdapterError, ValueError, OSError) as exc:
        return _simulated_history(clean, days, reason=str(exc))


def add_to_watchlist(conn: sqlite3.Connection, user_id: int, symbol: str) -> None:
    """Add symbol to user's watchlist."""
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    WatchlistRepository(conn).add(user_id=user_id, symbol=symbol, added_at=now_str)


def remove_from_watchlist(conn: sqlite3.Connection, user_id: int, symbol: str) -> bool:
    """Remove symbol strictly scoped to user_id; returns True if deleted."""
    return WatchlistRepository(conn).remove(user_id=user_id, symbol=symbol) > 0


def list_watchlist(
    conn: sqlite3.Connection,
    user_id: int,
    adapter: MarketDataAdapter | None = None,
) -> list[dict[str, Any]]:
    """List user's watchlist rows, each carrying exactly one REAL or SIMULATED badge (AC-29)."""
    rows = WatchlistRepository(conn).list_for_user(user_id=user_id)
    items: list[dict[str, Any]] = []
    for row in rows:
        quote = get_quote(row.symbol, adapter=adapter)
        items.append(
            {
                "symbol": row.symbol,
                "added_at": row.added_at,
                "price": quote["price"],
                "change_pct": quote["change_pct"],
                "label": quote["label"],
                "source": quote["source"],
            }
        )
    return items


def watchlist_action_db_path(
    db_path: str | Path | None,
    user_id: int,
    action: str,
    symbol: str = "",
) -> list[dict[str, Any]]:
    """UI-safe helper opening a DB connection for watchlist CRUD without exposing storage to UI."""
    conn = get_connection(db_path)
    try:
        if action == "add" and symbol:
            add_to_watchlist(conn, user_id, symbol)
        elif action == "remove" and symbol:
            remove_from_watchlist(conn, user_id, symbol)
        return list_watchlist(conn, user_id)
    finally:
        conn.close()
