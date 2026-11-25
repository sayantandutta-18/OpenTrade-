# System Architecture

Version: 1.0

## 1. Layers

```
+----------------------------------------------------------+
| UI layer (Streamlit pages, components, chat panel)       |
+----------------------------------------------------------+
        | calls only service functions
+----------------------------------------------------------+
| Service layer (auth, runs, data, analyst, chat, news)    |
+----------------------------------------------------------+
        | calls engine with plain data in, plain data out
+----------------------------------------------------------+
| Engine layer (book, flow, maker, impact, execution)      |
| Pure Python. No I/O. No UI imports.                      |
+----------------------------------------------------------+
        |
+----------------------------------------------------------+
| Storage (SQLite file for users, runs, chats, catalog)    |
| Results folder for saved run JSON (optional mirror)      |
+----------------------------------------------------------+

Adapters (outside the layers, called by services only):
  - Market data adapter (yfinance, Twelve Data)
  - News adapter (RSS, news API)
  - Email adapter (SMTP)
  - LLM adapter (provider SDK)
```

## 2. Dependency rules

- UI may import services. It never imports storage, adapters, or engine internals directly. It may import engine result types for display only.
- Services may import engine, storage, and adapters.
- Engine imports only the Python standard library and numpy (if needed).
- Adapters import no internal modules except config.
- Storage imports no service or UI modules.

A test in tests/test_architecture.py parses imports and fails on any violation.

## 3. Components

| Component | Module | Responsibility |
|---|---|---|
| Auth service | services/auth.py | Register, verify, login, lockout, sessions, reset, delete |
| Run service | services/runs.py | Build RunConfig, call engine, save result, list and load runs |
| Catalog service | services/catalog.py | Search, presets, comparison set limit |
| Market service | services/market.py | Quotes and history with REAL or SIMULATED label |
| News service | services/news.py | Headlines with demo or live mode and cache |
| Analyst service | services/analyst.py | Four prompts, demo answers, live LLM calls |
| Chat service | services/chat.py | Context building, guardrails, tool dispatch, confirmations, limits |
| Provenance | config.py | Labels and fingerprint used by every service |
| Scheduler (Phase 19) | worker.py | Runs long sweeps in a background process |

## 4. Data flows

### 4.1 Register and verify
1. UI posts name, email, password to auth service.
2. Auth service checks password rules, hashes with Argon2id, inserts user with email_verified_at NULL.
3. Auth service creates a verification token, stores its hash, sends the email through the email adapter.
4. User clicks the link. UI calls verify. Auth service marks the user verified and the token used.

### 4.2 Impact run
1. UI sends profile, sizes, seed, and optional name.
2. Run service builds RunConfig, computes fingerprint.
3. Run service calls engine impact function. Engine returns results and event-log hash. No I/O.
4. Run service attaches provenance (SYNTHETIC or CALIBRATED from profile) and schema_version.
5. If user is logged in and verified, run service writes the run row (result_json).
6. UI renders charts, each with its label.

### 4.3 Quote with fallback
1. UI requests quote for symbol.
2. Market service checks cache. On miss, calls market adapter with timeout.
3. On success: returns value with REAL, source name, and fetched_at.
4. On failure or no data: returns simulated value with SIMULATED, reason, and generated_at.

### 4.4 Chat turn
1. UI sends message and current screen context (selected companies, last run ID).
2. Chat service checks daily limit. Blocks if exceeded.
3. Chat service runs guardrail check (advice request, forbidden content).
4. Chat service builds context from saved results only, as JSON.
5. Chat service calls LLM adapter with system rules and the JSON. Streams tokens to UI.
6. If the model requests a tool action, chat service returns PENDING_CONFIRMATION. Action runs only on confirm.
7. Chat service stores messages in chat_messages.

## 5. Concurrency

- Streamlit runs one process with threads. Engine runs are pure, so they are thread-safe.
- SQLite runs in WAL mode to allow reads during writes.
- Long impact sweeps longer than 10 seconds run in the worker (Phase 19) and the UI polls status.

## 6. Deployment shape

- v1: one web process and one worker process, sharing the SQLite file on one host.
- v2: move the database to Postgres and the worker to a queue if load requires it.

## 7. Diagrams to produce

- Component diagram (Phase 0 end).
- Sequence diagram for the impact run (Phase 3 end).
- Sequence diagram for chat confirm flow (Phase 22 end).
Store diagrams as Mermaid text in this file.
