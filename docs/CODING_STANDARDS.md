# Coding Standards

Version: 1.0

## 1. Language and tools

- Python 3.11 or later. Use built-in type syntax (list[int], dict[str, int], int | None).
- Formatting: Black, line length 100.
- Linting: Ruff with rules E, F, I, B, UP, S (security), and SIM enabled.
- Types: mypy in strict mode for opentrade/engine and opentrade/services. Basic mode for ui.
- Tests: pytest only. No unittest classes.

## 2. Naming

| Item | Style | Example |
|---|---|---|
| Module | snake_case | order_flow.py |
| Class | CapWords | OrderBook |
| Function, variable | snake_case | submit_limit, best_bid |
| Constant | UPPER_SNAKE | MAX_COMPARE |
| Private helper | leading underscore | _match_level |
| Test function | test_ + behavior | test_ioc_never_rests |
| Database table | snake_case plural | watchlist_items |
| Database column | snake_case | email_verified_at |
| Environment variable | UPPER_SNAKE with OPENTRADE_ prefix for app settings | OPENTRADE_ENV |
| URL path | lowercase, hyphens | /api/v1/resend-verification |

Names describe what a thing is or does. Avoid abbreviations except widely known ones (id, url, api, csv).

## 3. Docstrings and comments

- Every public class and function has a docstring: one line for the summary, then Args, Returns, Raises when non-obvious.
- Comments explain why, not what. Delete comments that repeat the code.
- No commented-out code in the main branch.

## 4. Structure

- One responsibility per module. A module over 400 lines is a signal to split.
- A function over 40 lines is a signal to split.
- No global mutable state. Module-level constants are allowed.
- Dependency direction follows SYSTEM_ARCHITECTURE.md section 2. test_architecture.py enforces it.

## 5. Engine rules

- Prices are integer ticks. Only the display layer converts to currency.
- Randomness only through an injected random.Random instance. Never the global random module.
- No wall-clock time, file I/O, network, or printing inside engine functions.
- Every engine function that produces results also returns or records the event log hash input needed for reproducibility.
- Use dataclasses with frozen=True for configs and results.

## 6. Service rules

- Services return typed result objects, not raw dicts. Errors are raised as typed exceptions from opentrade/services/errors.py and mapped to the API error codes in API_SPEC.md.
- Every service function that touches user data takes user_id as an explicit argument. No implicit "current user" lookups inside repositories.
- Time is passed in or read from one clock function (services/clock.py), so tests can freeze it.

## 7. Security rules

- SQL: parameter binding only. No string formatting into SQL. Repositories are the only place SQL appears.
- Never log passwords, tokens, email bodies, chat text, or API keys. A logging filter removes known fields.
- Escape all user-supplied and third-party text in the UI. Do not use unsafe HTML rendering.
- Every query for user data includes user_id in the WHERE clause.
- Compare secrets with hmac.compare_digest.
- No eval, exec, or pickle on untrusted data.

## 8. Provenance rules

- Any function that returns a number returns it inside an object with a label field (REAL, CALIBRATED, SYNTHETIC) or receives the label from its caller.
- Labels are never removed, widened, or changed silently. A downgrade from REAL to SIMULATED must show a reason.
- A simulated value is never returned with a REAL label, even as a fallback.

## 9. Error handling

- Catch specific exceptions. A bare except is not allowed except at the top-level request handler, where it logs and returns INTERNAL.
- Do not swallow errors. Either handle them or let them propagate.
- External calls use the adapter timeout and retry policy (TRD.md section 6).

## 10. Git workflow

- Branch names: feature/<phase>-<short-name>, for example feature/p0-register.
- Commit subject: imperative, under 72 characters. Example: "Add Argon2 password hashing to register".
- Commit body: explain why when the change is not obvious. Reference the task ID (T0.3) and AC IDs.
- Pull request: one task or one closely related set. Includes the tests run and the AC IDs covered.
- Merge: squash merge into main after one approval and passing CI.
- Never force-push to main.

## 11. Review checklist

- [ ] Task ID and AC IDs listed in the pull request.
- [ ] Tests added or updated, and they fail without the change.
- [ ] No secrets in the diff.
- [ ] Provenance labels preserved for every new number.
- [ ] Layer rules respected (architecture test passes).
- [ ] SQL parameterized. User queries filtered by user_id.
- [ ] Copy follows UI_UX_GUIDELINES.md section 7.
- [ ] CHANGELOG.md updated under Unreleased.
- [ ] TASKS.md status updated.
