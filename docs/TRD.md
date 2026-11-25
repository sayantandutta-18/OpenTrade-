# Technical Requirements Document

Version: 1.0

## 1. Technology stack

| Layer | Choice | Version | Why |
|---|---|---|---|
| Language | Python | 3.11 or later | Strong finance and data libraries |
| Engine | Pure Python with dataclasses | Standard library | No dependency needed for the core |
| Hot loop (Phase 19) | Numba | Latest stable | Speed without changing language |
| Web UI | Streamlit | Latest stable | Charts, tabs, forms with little code |
| Password hashing | argon2-cffi | Latest stable | Argon2id is the recommended algorithm |
| Email | smtplib with a transactional SMTP provider | Standard library | No vendor lock-in |
| Database | SQLite via the standard sqlite3 module | Bundled with Python | No server to run |
| Migrations | Plain numbered SQL files and a small runner | | Simple and reviewable |
| Market data | yfinance | Latest stable | Free daily quotes and history |
| News | RSS feeds from public outlets, cached 15 minutes | | Free; demo fallback |
| LLM | Provider SDK behind an adapter in llm/adapter.py | | Swappable provider |
| Testing | pytest, Hypothesis, Playwright | Latest stable | Unit, property, and browser tests |
| Lint and format | Ruff and Black | Latest stable | Fast and standard |
| Type checks | mypy | Latest stable | Catches interface errors |

## 2. Key technical decisions

1. Prices are integer ticks. Conversion to currency happens at the display boundary only.
2. The engine has no imports from UI or services, so it can run in scripts and tests.
3. Each run is a pure function of its config and seed. No wall-clock time or global random state is used inside the engine.
4. Every external call goes through an adapter with a 5-second timeout, at most two retries with backoff, and a fallback path.
5. Saved results are JSON with a schema_version field. Loading an older version runs a migration function.
6. Passwords use Argon2id with library defaults. Session IDs are random 256-bit tokens; only their SHA-256 hash is stored.
7. Secrets come from environment variables only.

## 3. Engine details

- Order IDs are sequential integers within a book instance.
- Timestamps inside the engine are event counters, not wall-clock times.
- Random draws come from a random.Random instance seeded from the run config.
- Each run writes an event log (list of tuples). Its SHA-256 is saved in the result for reproducibility checks.

## 4. Performance targets

| Operation | Target |
|---|---|
| Single order injection | Under 10 ms |
| Impact sweep, 20 sizes, v1 pure Python | Under 30 s |
| Impact sweep, 20 sizes, after Numba | Under 3 s |
| Page first content | Under 3 s on mid-range phone |
| Login request | Under 500 ms, excluding the hash cost budget (Argon2 target 250 ms) |

## 5. Caching

- Quotes and history: cached 15 minutes per symbol, keyed by symbol and date.
- News: cached 15 minutes per feed.
- Analyst live answers: cached per (prompt, input hash) for 24 hours.
- Catalog: loaded once at startup from data/catalog.csv.

## 6. Error handling

- Every API response uses the error shape in API_SPEC.md.
- Unhandled exceptions are logged with request ID and returned as 500 INTERNAL with no stack trace to the user.
- External failures never crash a page. They produce a labeled fallback.

## 7. Logging

- Structured JSON logs, one line per event.
- Fields: timestamp, level, request_id, event, user_id (hashed), duration_ms.
- Never logged: passwords, tokens, email bodies, chat message text, API keys.

## 8. Configuration

All settings come from environment variables, validated at startup. The app refuses to start if a required variable is missing (see ENVIRONMENT.md).

## 9. Open technical questions

| Question | Owner | Decide by |
|---|---|---|
| Which news provider for live mode (RSS only, or a paid API) | Product | Phase 8 |
| Which LLM provider and model | Product | Phase 16 |
| Move from SQLite to Postgres | Engineering | When active accounts exceed 300 |
| Add Redis cache | Engineering | When sweeps run concurrently for many users |
