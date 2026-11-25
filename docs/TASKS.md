# Tasks

Version: 1.0
Status key: TODO, DOING, DONE, BLOCKED.
Rule: a task is DONE only when every listed AC test passes and the full suite is green.
Work in ID order within each phase. Do not start a task whose dependency is not DONE.

## Phase 0: Foundations and accounts

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T0.1 | Create project skeleton per PROJECT_STRUCTURE.md, pyproject.toml, .gitignore, .env.example, tooling (ruff, black, mypy, pytest) | none | architecture test passes | DONE |
| T0.2 | Settings loader with validation (ENVIRONMENT.md); refuse to start if required values missing | T0.1 | Settings test | DONE |
| T0.3 | Database connection (WAL, foreign keys), migration runner, 0001_init.sql for users, sessions, auth_tokens | T0.2 | migration test | DONE |
| T0.4 | Password rules and Argon2id hashing (security.py) | T0.3 | AC-2, AC-3 | DONE |
| T0.5 | Register endpoint and service; validation errors per API_SPEC | T0.4 | AC-1, AC-2, AC-3, AC-43 | DONE |
| T0.6 | Email verification: token creation, email adapter (console in local), verify endpoint, resend limit. Test required: a duplicate registration must not send a verification email, but must notify the real owner. This test is part of T0.6, not T0.5. | T0.5 | Verification tests; FR-3 | DONE |
| T0.7 | Login with lockout and IP rate limit | T0.5 | AC-4 | DONE |
| T0.8 | Sessions: cookie issue, expiry, sliding window, logout, logout-all | T0.7 | AC-9 | DONE |
| T0.9 | CSRF middleware (token endpoint, header check) | T0.8 | CSRF test | DONE |
| T0.10 | Password reset: forgot (same reply), reset (single use, 30 min) | T0.6, T0.9 | AC-5, AC-8 | DONE |
| T0.11 | Profile: view, change name and email (re-verify), change password | T0.9 | FR-8 test | DONE |
| T0.12 | Account deletion (password confirm) with cascade | T0.11 | AC-6 | DONE |
| T0.13 | Per-user access rule: 404 for other users' records | T0.12 | AC-7 | DONE |
| T0.14 | Security headers and log filter (no secrets in logs) | T0.9 | Header test; log filter test | DONE |
| T0.15 | RunConfig, fingerprint, schema_version, save_result with provenance (config.py) | T0.2 | AC-21 (partial), reproducibility test | DONE |
| T0.16 | Prototype banner component and home page with Register, Log in, Demo buttons | T0.9 | AC-42; AC-10 (manual) | DONE |
| T0.17 | Register, login, verify, forgot, and reset pages with privacy note | T0.16 | Browser test for flow 2 to 4 | DONE |

## Phase 1: Order book

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T1.1 | Book structure: FIFO queues per price level, sorted sides, integer ticks | T0.15 | AC-11 | DONE |
| T1.2 | Matching for limit, market, IOC, FOK, cancel | T1.1 | AC-12, AC-13, AC-14, AC-15 | DONE |
| T1.3 | Determinism: event log and hash; same seed same hash | T1.2 | AC-16 | DONE |
| T1.4 | No crossed book invariant | T1.2 | AC-17 | DONE |
| T1.5 | Lot sizes, stop orders, iceberg orders, self-trade prevention | T1.4 | Unit tests per rule | DONE |
| T1.6 | Queue-position tracking for a tagged order | T1.5 | Unit test | DONE |
| T1.7 | Execution metrics & slippage attribution (metrics.py) | T1.6 | FR-22, FR-25, FR-52 | DONE |
| T1.8 | Multi-size / multi-strategy simulation runner (runner.py) | T1.7 | FR-27, FR-52 | DONE |
| T1.9 | Reproducibility & determinism verification | T1.8 | AC-16, AC-21 | DONE |
| T1.10 | Preset liquidity profiles (profiles.py) | T1.5 | FR-37, FR-52 | DONE |
| T1.11 | Run persistence service (runs.py, repositories.py) | T1.8, T0.13 | AC-7, AC-21 | DONE |
| T1.12 | Phase 1 integration & performance benchmark gate | T1.11 | TRD.md §4 | DONE |

## Phase 2: Order flow

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T2.1 | Poisson arrivals for limit, market, cancel events | T1.6 | Seeded rate test | TODO |
| T2.2 | Power-law placement distances from profile | T2.1 | Distribution test | TODO |
| T2.3 | Noise, momentum, and informed trader types | T2.2 | Each type unit test | TODO |
| T2.4 | Calibrate default profile so spread and depth are in range | T2.3 | Spread and depth test (3 profiles) | TODO |

## Phase 3: Impact

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T3.1 | Inject market order and measure slippage against arrival mid | T2.4 | Slippage unit test | TODO |
| T3.2 | Impact sweep (at least 6 sizes) and log-log fit with 95 percent CI | T3.1 | AC-18, AC-19, AC-20 | TODO |
| T3.3 | Temporary and permanent impact, decay curve | T3.2 | Decay test | TODO |
| T3.4 | Run service: save impact run with fingerprint and provenance | T3.2, T0.15 | AC-21 | TODO |
| T3.5 | Simulator screen (book view, depth chart, inject button) | T3.4 | Browser test; AC-41 | TODO |
| T3.6 | Impact lab screen with chart, exponent, plain-language sentence | T3.5 | AC-22 (manual) | TODO |

## Phase 4 to 6: Companies, map, profiles

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T4.1 | Load catalog.csv (about 190 rows, source and date columns) | T0.3 | Catalog load test | TODO |
| T4.2 | Search endpoint and presets (presets.json) | T4.1 | AC-23, AC-26 | TODO |
| T4.3 | Comparison set with six-company limit | T4.2 | AC-24 | TODO |
| T5.1 | Universe map with pins, zoom, click to add or remove | T4.3 | AC-25; flow 5 browser test | TODO |
| T6.1 | Liquidity profiles (JSON schema, calibration script from yfinance) | T4.1 | Schema test | TODO |
| T6.2 | Factor radar scoring with missing values | T6.1 | AC-27 (manual) | TODO |

## Phase 7 to 8: Market data and news

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T7.1 | Market adapter with timeout, retry, cache | T4.1 | Contract test with fixture | TODO |
| T7.2 | Quote, history, and watchlist services with labels | T7.1 | AC-28, AC-29 | TODO |
| T7.3 | Market data panel screen | T7.2 | Browser test | TODO |
| T8.1 | News adapter (RSS) with cache and demo fallback | T4.1 | AC-30, AC-31 | TODO |
| T8.2 | News panel with demo and live toggle | T8.1 | Browser test; flow 7 | TODO |

## Phase 9 to 15: Dynamics and research

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T9.1 | Shock events in the flow | T3.4 | Scheduled event test | TODO |
| T9.2 | News lab screen: calm versus news slippage with CI | T9.1 | Comparison test | TODO |
| T10.1 | Hawkes arrivals option | T2.1 | Burstiness test | TODO |
| T11.1 | Endogenous mid from order imbalance | T1.6 | Net-buying test | TODO |
| T12.1 | Avellaneda-Stoikov maker with inventory and P&L split | T11.1 | P&L sum test | TODO |
| T13.1 | Execution strategies and shortfall ranking | T12.1 | Full-fill test per strategy | TODO |
| T14.1 | Correlation service, verdict, effective holdings | T7.2 | AC-32, AC-33 | TODO |
| T14.2 | Correlation overview and concentration-vs-count screens | T14.1 | Browser test | TODO |
| T15.1 | Multi-book cross-impact and correlation emergence | T11.1 | Correlation test | TODO |

## Phase 16 to 22: AI, validation, polish

| ID | Task | Depends on | ACs | Status |
|---|---|---|---|---|
| T16.1 | Analyst service: four prompts, demo answers, live adapter | T14.1 | AC-34, AC-35, AC-36 | TODO |
| T16.2 | Analyst screen with mode badge | T16.1 | Browser test | TODO |
| T17.1 | Basic assistant: screen context, read-only answers | T16.1 | Refusal test (AC-38) | TODO |
| T18.1 | Stylized-fact validation (fat tails, clustering, spread, signature plot) | T3.4 | Pass or fail test per fact | TODO |
| T19.1 | Numba versions of hot loops, equal output to pure Python | T3.2 | Equality test; performance targets | TODO |
| T20.1 | Run history screen and re-run with fingerprint check | T3.4 | Flow 10 browser test | TODO |
| T20.2 | Tour and About screens | T16.2 | Browser test | TODO |
| T20.3 | Replay mode for real historical data | T18.1 | Replay test | TODO |
| T21.1 | Narrative summary, every number checked against saved results | T16.1 | Number-match test | TODO |
| T22.1 | Full chatbot: streaming, citations, guardrails | T17.1 | AC-37, AC-38 | TODO |
| T22.2 | Chat actions with confirmation and expiry | T22.1 | AC-39 | TODO |
| T22.3 | Chat limits and history clear | T22.1 | AC-40 | TODO |
| T-X.1 | Provenance label walk across all screens | all UI tasks | AC-41 | TODO |
| T-X.2 | Accessibility scan (axe) across all screens | all UI tasks | UI_UX_GUIDELINES section 9 | TODO |
| T-X.3 | Security baseline scan before release | all | SECURITY section 10 | TODO |
