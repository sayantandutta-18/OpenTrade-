-- Migration 0007: Terms & Conditions acceptance timestamp and INR subscriptions
ALTER TABLE users ADD COLUMN terms_accepted_at TEXT;

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_code TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    amount_inr INTEGER NOT NULL,
    billing_cycle TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    payment_ref TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status ON subscriptions(user_id, status);
