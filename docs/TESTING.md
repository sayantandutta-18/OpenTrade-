# Testing

Version: 1.0

## 1. Test levels

| Level | Tool | What it covers | Where it runs |
|---|---|---|---|
| Unit | pytest | Single functions: book rules, fingerprint, password checks, metrics | Every commit |
| Property | Hypothesis | Invariants: no crossed book, FIFO, sorted sides, non-negative quantities | Every commit |
| Integration | pytest with a temporary SQLite file | Services with storage, migrations | Every commit |
| Contract | pytest with recorded fixtures | Adapters parse real response shapes | Every commit |
| Browser | Playwright (Chromium, mobile emulation 360 px) | Register, log in, impact run, chat confirm | Every merge |
| Accessibility | axe-core through Playwright | WCAG 2.1 AA rules | Every merge |
| Reproducibility | pytest | Same seed gives same event-log hash | Every commit |
| Provenance | pytest render walk | Every number has a label (AC-41) | Every merge |
| Architecture | pytest, import parser | Layer dependency rules | Every commit |
| Security | pytest plus OWASP ZAP baseline | Auth, CSRF, headers, cross-user access | Before each release |
| Performance | pytest-benchmark | Targets in TRD.md section 4 | Nightly |

## 2. Required tests by phase

| Phase | Must pass before the phase is DONE |
|---|---|
| 0 Foundations and accounts | AC-1 to AC-10; reproducibility test for RunConfig; provenance saved in every result; architecture test |
| 1 Order book | AC-11 to AC-17 |
| 2 Flow | Spread and depth within the profile's target range for 3 default profiles (seeded) |
| 3 Impact | AC-18 to AC-21; AC-20 exponent check with seed 42 |
| 4 Catalog | AC-23, AC-26 |
| 5 Map | AC-25; map click adds and removes companies |
| 6 Profiles and radar | AC-27 (manual); profile JSON schema validation |
| 7 Market data | AC-28, AC-29 |
| 8 News | AC-30, AC-31 |
| 9 Shocks | Shock events fire at scheduled times in a seeded run |
| 10 Hawkes | Inter-arrival coefficient of variation above Poisson's in a seeded run |
| 11 Endogenous price | Net buying raises mid in at least 90 percent of seeded trials |
| 12 Maker | P&L components sum to total P&L within 1e-9 |
| 13 Execution | Each strategy fills the full quantity in the test book |
| 14 Diversification | AC-32, AC-33 |
| 15 Cross-impact | Correlation of two linked books exceeds that of two unlinked books |
| 16 Analyst | AC-34 to AC-36 |
| 17 Basic chat | Refusal test; citation test |
| 18 Validation | Each stylized-fact check returns pass or fail with a value |
| 19 Performance | TRD.md targets; Numba output equals pure Python output |
| 20 Interface and history | AC-42; browser flow for tour and run history |
| 21 Summary | Every number in summary text appears in saved results (AC-36 method) |
| 22 Chatbot | AC-37 to AC-40 |

## 3. Rules

1. No test calls a live API. Adapters are tested with recorded fixtures in tests/fixtures/. A network-blocking fixture is active for all tests by default; tests that need the network must opt in and are excluded from CI.
2. Tests are deterministic. Each test sets its own seed.
3. A test name states the behavior: test_fok_order_leaves_book_unchanged, not test_fok_2.
4. Each acceptance-criteria test includes the AC ID in its docstring, so reports link back to the spec.
5. Flaky tests are fixed or removed within one day. They are never retried silently.
6. Bugs get a regression test before the fix is merged.

## 4. Coverage targets

| Area | Line coverage |
|---|---|
| engine/ | 85 percent minimum |
| services/ | 75 percent minimum |
| storage/ | 80 percent minimum |
| Overall | 75 percent minimum |

Coverage is a floor, not a goal. A test must check behavior, not just run lines.

## 5. Test data

- data/demo/ files are used by demo-mode tests.
- tests/fixtures/ holds recorded HTTP responses from each adapter, with the date recorded in a comment.
- Engine tests use small hand-built books (3 to 5 levels) so results can be checked by hand.

## 6. Commands

```
pytest                          # unit, property, integration, contract, architecture
pytest -m "not browser"         # skip Playwright
pytest -m browser               # browser and accessibility tests
pytest tests/engine -q          # engine only
pytest --cov=opentrade --cov-report=term-missing
ruff check . && black --check . && mypy opentrade
```

## 7. Definition of done for a test run

- All non-browser tests pass.
- Coverage meets section 4.
- ruff, black, and mypy report no errors.
- For merges to main: browser and accessibility tests pass.
