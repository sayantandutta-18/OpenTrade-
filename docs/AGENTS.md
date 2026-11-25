# Instructions for AI Coding Agents

Version: 1.0
Applies to: Google Antigravity, and any other AI coding agent working in this repository.

## 1. Your job

Build OpenTrade one task at a time, from TASKS.md, following the specification in this docs/ folder. The specification is the source of truth. If the code and the spec disagree, the spec wins unless the user says otherwise.

## 2. Before you start any task

1. Read README.md (2 minutes).
2. Read the task in TASKS.md. Note its ID, its acceptance criteria (AC IDs), and its phase.
3. Read the spec sections the task names. Common mappings:
   - Accounts: SRS section 1, API_SPEC section 2, DATABASE users/sessions/auth_tokens, SECURITY sections 3 to 5.
   - Engine: SRS section 2, CODING_STANDARDS section 5, ACCEPTANCE_CRITERIA AC-11 to AC-17.
   - Impact: SRS section 3, ACCEPTANCE_CRITERIA AC-18 to AC-21.
   - UI: UI_UX_GUIDELINES.md, USER_FLOW.md for the relevant flow.
4. Read DECISIONS.md to avoid reversing a settled decision.
5. Check PROJECT_STRUCTURE.md for where new files go.

If any of these reads reveals a conflict or missing information, stop and ask (section 9).

## 3. Hard rules (never break these)

1. Every number shown to a user carries a provenance label: REAL, CALIBRATED, or SYNTHETIC. Demo and live content also carry DEMO or LIVE.
2. Never show simulated data as real. If a live source fails, fall back and label it SIMULATED with the reason.
3. Passwords are hashed with Argon2id. Never store, log, or return a plain-text password or a hash.
4. Session tokens, reset tokens, and verification tokens are random, and only their SHA-256 hashes are stored.
5. Every database query for user data filters by user_id.
6. Use parameterized SQL only.
7. The engine has no imports from ui, services, adapters, or storage. No I/O inside the engine.
8. Prices in the engine are integers (ticks).
9. No live API calls in tests. Use fixtures. Demo mode makes zero network calls.
10. LLM output never sets a number. Numbers come from computed results. Chat and analyst answers must cite run IDs or data sources for every number.
11. Do not give investment advice in any text the app produces. Do not recommend buying or selling.
12. Do not add a dependency without adding a DECISIONS.md entry and a pyproject.toml change in the same pull request.
13. Do not commit secrets. Do not write API keys into code, tests, or examples.
14. Do not disable or delete a failing test to make a build pass. Fix the code or report the conflict.

## 4. Working method for each task

1. Confirm the task ID and its AC IDs.
2. Write or update the tests first. Each test names the AC ID in its docstring. Run them and confirm they fail for the right reason.
3. Implement the smallest change that makes the tests pass.
4. Run the full suite: pytest, ruff check ., black --check ., mypy opentrade.
5. Check the rules in section 3 against your change.
6. Update CHANGELOG.md under Unreleased (one line per user-visible change).
7. Update TASKS.md: set the task to DONE only if all its AC tests pass.
8. Report back in the format in section 6.

## 5. Order of work

Follow TASKS.md order. Do not start a task whose dependencies are not DONE. Within Phase 0, the order is: skeleton (T0.1), database and migrations (T0.2), registration (T0.3), verification (T0.4), login and lockout (T0.5), sessions and CSRF (T0.6), reset (T0.7), profile and delete (T0.8), cross-user tests (T0.9), then run config and provenance (T0.10 to T0.12).

Accounts come first because every saved feature depends on them.

## 6. Report format (after each task)

```
Task: T0.3 Registration
ACs covered: AC-1, AC-2, AC-3
Files changed: list
Tests run: command and result counts
Rules checked: section 3 items relevant to this change (write "none" if none)
Open questions: list, or "none"
Next task suggested: ID
```

Keep the report short. Do not paste whole files unless asked.

## 7. Style

Follow CODING_STANDARDS.md. In particular: type hints on public functions, docstrings on public items, Black and Ruff clean.

## 8. Copy and UX

Follow UI_UX_GUIDELINES.md section 7 for all user-facing text. Keep button labels as verbs. Never use "guaranteed," "will rise," or "should buy."

## 9. When to stop and ask

Stop and ask the user before:
- Changing any requirement, acceptance criterion, or number in the spec.
- Adding a paid service, a new external API, or a new dependency.
- Changing the database engine or the front-end framework.
- Deleting data or migrations.
- Anything that touches real money, brokers, or personal data beyond the list in SECURITY.md section 8.
- Any case where two spec documents disagree.

When asking, state the question, the options, and what you would recommend.

## 10. Things you must not invent

- Market data values, news headlines, or analyst text beyond the bundled demo files.
- Company data beyond data/catalog.csv. Mark missing fields as missing.
- Test results. Run the tests and report what happened.
