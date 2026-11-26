-- Migration 0003: Watchlists
CREATE TABLE IF NOT EXISTS watchlist_items (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist_items(user_id);
