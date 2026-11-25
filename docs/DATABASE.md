# Database

Version: 1.0
Engine: SQLite 3 with WAL mode and foreign keys enabled (PRAGMA foreign_keys = ON on every connection).
Timestamps: UTC, ISO 8601 text, for example 2026-11-24T17:23:00Z.
IDs: INTEGER PRIMARY KEY unless stated.

## 1. Tables

### users
| Column | Type | Null | Rules |
|---|---|---|---|
| id | INTEGER | no | Primary key |
| name | TEXT | no | 1 to 80 characters |
| email | TEXT | no | Unique, stored lowercase, max 254 |
| password_hash | TEXT | no | Argon2id string |
| email_verified_at | TEXT | yes | NULL until verified |
| failed_logins | INTEGER | no | Default 0, reset on success |
| locked_until | TEXT | yes | Lock end time |
| created_at | TEXT | no | |
| updated_at | TEXT | no | |

Index: unique index on email.

### sessions
| Column | Type | Null | Rules |
|---|---|---|---|
| id | INTEGER | no | Primary key |
| user_id | INTEGER | no | FK users.id ON DELETE CASCADE |
| token_hash | TEXT | no | SHA-256 of the cookie token, unique |
| created_at | TEXT | no | |
| expires_at | TEXT | no | Created plus 14 days, sliding on activity to a max of 30 days |
| last_seen_at | TEXT | no | |
| user_agent_hash | TEXT | yes | SHA-256 of user agent, for "log out other devices" |

Index: unique on token_hash; index on user_id.

### auth_tokens
Used for email verification and password reset.
| Column | Type | Null | Rules |
|---|---|---|---|
| id | INTEGER | no | Primary key |
| user_id | INTEGER | no | FK users.id ON DELETE CASCADE |
| purpose | TEXT | no | "verify_email" or "reset_password" |
| token_hash | TEXT | no | SHA-256 of the emailed token, unique |
| expires_at | TEXT | no | verify: 24 hours; reset: 30 minutes |
| used_at | TEXT | yes | Set on first use |
| created_at | TEXT | no | |

### runs
| Column | Type | Null | Rules |
|---|---|---|---|
| id | TEXT | no | UUID4, primary key |
| user_id | INTEGER | no | FK users.id ON DELETE CASCADE |
| name | TEXT | no | 1 to 120 characters |
| seed | INTEGER | no | |
| config_json | TEXT | no | Full RunConfig as JSON |
| fingerprint | TEXT | no | First 12 hex chars of SHA-256 of config |
| provenance | TEXT | no | REAL, CALIBRATED, or SYNTHETIC |
| result_json | TEXT | no | Results with schema_version |
| schema_version | INTEGER | no | Starts at 1 |
| created_at | TEXT | no | |

Index: (user_id, created_at).

### watchlist_items
| Column | Type | Null | Rules |
|---|---|---|---|
| user_id | INTEGER | no | FK users.id ON DELETE CASCADE |
| symbol | TEXT | no | FK company_catalog.symbol |
| added_at | TEXT | no | |

Primary key: (user_id, symbol).

### chat_messages
| Column | Type | Null | Rules |
|---|---|---|---|
| id | INTEGER | no | Primary key |
| user_id | INTEGER | no | FK users.id ON DELETE CASCADE |
| role | TEXT | no | "user", "assistant", or "system_action" |
| content | TEXT | no | Max 4000 characters |
| created_at | TEXT | no | |
| deleted_at | TEXT | yes | Soft delete for "clear history" |

Index: (user_id, created_at).

### pending_actions
Chat actions awaiting confirmation.
| Column | Type | Null | Rules |
|---|---|---|---|
| id | TEXT | no | UUID4, primary key |
| user_id | INTEGER | no | FK users.id ON DELETE CASCADE |
| action | TEXT | no | "save_run", "delete_run", or "add_company" |
| payload_json | TEXT | no | |
| status | TEXT | no | PENDING, CONFIRMED, CANCELLED, or EXPIRED |
| expires_at | TEXT | no | Created plus 10 minutes |
| created_at | TEXT | no | |

### company_catalog
| Column | Type | Null | Rules |
|---|---|---|---|
| symbol | TEXT | no | Primary key |
| name | TEXT | no | |
| sector | TEXT | no | One of the 10 sector names used in the app |
| hq_city | TEXT | no | |
| hq_country | TEXT | no | |
| lat | REAL | no | |
| lon | REAL | no | |
| market_cap_usd_bn | REAL | yes | Null if unknown |
| source | TEXT | no | Where the row came from |
| source_date | TEXT | no | Date of the source |

### audit_log
| Column | Type | Null | Rules |
|---|---|---|---|
| id | INTEGER | no | Primary key |
| user_id | INTEGER | yes | Null for anonymous events; no FK so logs survive deletion |
| event | TEXT | no | e.g. LOGIN_FAILED, PASSWORD_RESET_REQUESTED, ACCOUNT_DELETED |
| ip_hash | TEXT | yes | SHA-256 of IP with a server salt |
| created_at | TEXT | no | |

Audit rows contain no passwords, tokens, email bodies, or chat text.

## 2. Migrations

- Files live in storage/migrations/ named 0001_init.sql, 0002_..., applied in order.
- A table schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT) records what ran.
- Each migration runs in one transaction. A failed migration rolls back and stops startup.
- Migrations are additive where possible. Column drops wait one release.

## 3. Account deletion

Deleting a user removes rows in: sessions, auth_tokens, runs, watchlist_items, chat_messages, pending_actions (all by CASCADE). audit_log keeps event rows with user_id set to NULL for the deleted account.

## 4. Backups

Use SQLite's online backup API nightly. Keep 14 days. Test restore quarterly.
