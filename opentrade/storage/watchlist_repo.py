"""Repository for per-user watchlist_items table using parameterized SQL (T7.2)."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class WatchlistRow:
    """Database row for watchlist_items."""

    user_id: int
    symbol: str
    added_at: str


class WatchlistRepository:
    """SQLite repository for user-scoped watchlist items."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, user_id: int, symbol: str, added_at: str) -> WatchlistRow:
        """Insert or ignore a symbol into a user's watchlist."""
        clean = symbol.strip().upper()
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO watchlist_items (user_id, symbol, added_at)
                VALUES (?, ?, ?);
                """,
                (user_id, clean, added_at),
            )
            return WatchlistRow(user_id=user_id, symbol=clean, added_at=added_at)
        finally:
            cursor.close()

    def remove(self, user_id: int, symbol: str) -> int:
        """Delete a symbol strictly scoped to user_id; returns deleted row count."""
        clean = symbol.strip().upper()
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM watchlist_items WHERE user_id = ? AND symbol = ?;",
                (user_id, clean),
            )
            return cursor.rowcount
        finally:
            cursor.close()

    def list_for_user(self, user_id: int) -> list[WatchlistRow]:
        """List all watchlist items for user_id in addition order."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT user_id, symbol, added_at
                FROM watchlist_items
                WHERE user_id = ?
                ORDER BY added_at ASC, symbol ASC;
                """,
                (user_id,),
            )
            return [
                WatchlistRow(user_id=r[0], symbol=r[1], added_at=r[2]) for r in cursor.fetchall()
            ]
        finally:
            cursor.close()
