# Decision Log

Version: 1.0
Format: each entry has an ID, date, status (Proposed, Accepted, Superseded, Deferred), context, decision, reasons, and consequences. Superseded decisions are kept and marked, never deleted.

## ADR-001: Python for the engine and server

- Date: 2026-11-24
- Status: Accepted
- Context: The engine needs fast iteration, finance and data libraries, and a path to speed-ups.
- Decision: Python 3.11 or later for all server and engine code.
- Reasons: Strong numeric libraries, readable for students, simple tests.
- Consequences: Hot loops may need Numba (ADR-006). Front end is a separate choice (ADR-003).

## ADR-002: Integer tick prices in the engine

- Date: 2026-11-24
- Status: Accepted
- Context: Price comparison in the matching logic must be exact.
- Decision: Prices are integers counting ticks. Currency conversion happens only for display.
- Reasons: Avoids floating-point errors in matching and in FIFO ordering.
- Consequences: Tick size is part of each profile and config.

## ADR-003: Streamlit for the first front end

- Date: 2026-11-24
- Status: Accepted
- Context: The team needs a working UI quickly, with charts, tabs, forms, and a map.
- Decision: Streamlit for v1.
- Reasons: Fastest route to a complete app with Python only.
- Consequences: Mobile layout and motion are limited. Custom CSS in ui/theme.py handles the main mobile needs. Revisit with ADR-007 if the tour or layout needs more control.

## ADR-004: SQLite for v1 storage

- Date: 2026-11-24
- Status: Accepted
- Context: The app needs users, sessions, runs, and chat history, with few concurrent writes at launch.
- Decision: SQLite in WAL mode, with numbered SQL migrations.
- Reasons: No server to run; enough for a few hundred active accounts.
- Consequences: Move to Postgres when DEPLOYMENT.md scaling trigger is met (new ADR at that time).

## ADR-005: Accounts are built first

- Date: 2026-11-24
- Status: Accepted
- Context: Saved runs, watchlists, and chat need an owner.
- Decision: Registration, verification, login, and password reset are Phase 0 tasks T0.3 to T0.13.
- Reasons: Avoids retrofitting user_id into every feature later.
- Consequences: Demo mode must work with no account. Every service takes user_id explicitly.

## ADR-006: Numba for the hot loop

- Date: 2026-11-24
- Status: Proposed
- Context: Pure Python sweeps may take over 30 seconds for large experiments.
- Decision: Use Numba for the matching and sweep loops in Phase 19 only after pure Python is correct.
- Reasons: Speed without a second language.
- Consequences: New dependency. Adopt only if performance targets in TRD.md are missed. Numba output must equal pure Python output (test in T19.1).

## ADR-007: React front end (deferred)

- Date: 2026-11-24
- Status: Deferred
- Context: Streamlit may limit the mobile tour and fine layout control.
- Decision: Not in v1. Reconsider after Phase 20 with user feedback.
- Reasons: Keeps v1 focused.
- Consequences: If adopted, the API_SPEC.md endpoints become the contract for the new front end.

## ADR-008: Labels over hidden simulation

- Date: 2026-11-24
- Status: Accepted
- Context: Users must not mistake simulated data for market data.
- Decision: Show every simulated value with a visible label. Never hide the fact that data is simulated.
- Reasons: Core product promise (IDEA.md).
- Consequences: Busier UI. Enforced by AC-41 render test.

## ADR-009: Argon2id for passwords

- Date: 2026-11-24
- Status: Accepted
- Context: Password storage must resist offline attacks.
- Decision: argon2-cffi with library defaults for Argon2id.
- Reasons: Current recommended algorithm; library handles parameters and rehashing.
- Consequences: Login takes about 250 ms by design. Rehash on login when parameters change.

## ADR-010: Session cookies, not JWT

- Date: 2026-11-24
- Status: Accepted
- Context: The app is a single web service with server-side state.
- Decision: Random session tokens in HttpOnly cookies, stored as hashes in the database.
- Reasons: Revocation is immediate (logout-all, password change). JWTs are hard to revoke.
- Consequences: Each request reads the sessions table. Acceptable at v1 scale.

## ADR-011: LLM never sets numbers

- Date: 2026-11-24
- Status: Accepted
- Context: Language models can invent figures.
- Decision: Numbers come from computed results only. The model receives them as JSON and must not introduce new numbers. Tests check this (AC-36).
- Reasons: Trust and the core promise.
- Consequences: Some answers are less fluent. Accepted.

## ADR-012: Data sources are optional

- Date: 2026-11-24
- Status: Accepted
- Context: Free data sources can fail or change terms.
- Decision: Every external source is optional. With none configured, the app runs in demo and simulation mode.
- Reasons: Reliability and cost control.
- Consequences: Adapters must implement fallback labels.

## ADR-013: Bundled common-passwords list from SecLists

- Date: 2026-11-25
- Status: Accepted
- Context: Registration and password changes must reject common passwords to prevent credential stuffing and brute force attacks (SECURITY.md section 3, AC-2) without making network calls.
- Decision: Bundle the common passwords list at data/common_passwords.txt sourced from SecLists (Passwords/Common-Credentials/10k-most-common.txt, MIT license).
- Reasons: Curated community list, offline availability, zero network latency or external API dependencies during password validation.
- Consequences: The upstream SecLists 10k-most-common.txt file contains 10,001 unique, non-blank ASCII lines (0 duplicates, 0 blank lines). Entry #10,001 is the real password 'eyphed'. The file is preserved byte-for-byte (73,026 bytes, 10,001 lines, SHA-256: 68782d6a4a19a4768d5f15dd66bd534e7a33055cc755411e33f16d18c50fdcce) and loaded into memory as a normalized case-insensitive set for instant lookups.

## ADR-014: Registration does not reveal whether an email exists

- Date: 2026-11-25
- Status: Accepted
- Context: SECURITY.md T-5 (account enumeration).
- Decision: A new registration and a duplicate registration return the same status and same response body, with no id field and the same message: "If this email can be registered, a verification link has been sent." No row is created for duplicates. The real owner of an existing email receives a notice, sent in T0.6.
- Reasons: Prevent attackers from discovering registered account emails via registration attempts.
- Consequences:
  - T0.5 duplicate-email behaviour changes from 409 EMAIL_TAKEN to the same 201 response as a new registration.
  - T0.6 must add the notification to the real owner. Until T0.6 is DONE, an existing user is not told that someone tried to register with their email. This gap is accepted only until T0.6.
  - AC-43 is added to docs/ACCEPTANCE_CRITERIA.md.
  - Timing similarity is not measured by an automated test. This is a known gap.
  - register_user returns the same UserView type for new and duplicate registrations, so a caller cannot tell them apart. Any future email sending (T0.6) must check existence separately and must not depend on the return value. Note this as a constraint for T0.6.

## ADR-015: Suppression of Ruff Bandit rules S105 and S106 in tests

- Date: 2026-11-25
- Status: Accepted
- Context: Ruff Bandit rules S105 and S106 flag hardcoded password strings and function calls using token/password parameters. Test fixtures for authentication, hashing, and password rules necessarily use synthetic sample passwords and dummy token strings.
- Decision: Suppress S101 (assert statements), S105 (hardcoded password strings), and S106 (hardcoded password function arguments) for tests/* via [tool.ruff.lint.per-file-ignores] in pyproject.toml.
- Reasons: Allows testing password validation, hashing algorithms, and token flows with explicit test inputs without triggering false-positive linter errors, while keeping strict secret scanning and bandit rules enforced across all production application code.
- Consequences: Production code under opentrade/ remains strictly covered by S105/S106. Tests must still avoid real production credentials per docs/SECURITY.md.
