-- Migration 0004: Chat messages and pending actions
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system_action')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created
    ON chat_messages(user_id, created_at);

CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('save_run', 'delete_run', 'add_company')),
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED')),
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pending_actions_user
    ON pending_actions(user_id, status);
