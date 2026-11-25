# Project Structure

Version: 1.0
This is the exact layout to create in Phase 0 (T0.1). Empty placeholder files may contain only a module docstring until their phase.

```
opentrade/
├── README.md                         Project summary and setup
├── pyproject.toml                    Package metadata, dependencies, tool config
├── .env.example                      Every variable, placeholder values
├── .gitignore                        Ignores .env, data/*.db, results/, .venv
├── opentrade/
│   ├── __init__.py
│   ├── config.py                     Settings loader, RunConfig, Provenance, fingerprint, save_result
│   ├── engine/                       Pure logic. No I/O. No UI.
│   │   ├── __init__.py
│   │   ├── book.py                   Order book and matching (Phase 1)
│   │   ├── flow.py                   Poisson flow, power law, trader types (Phase 2)
│   │   ├── impact.py                 Impact sweep and fits (Phase 3)
│   │   ├── hawkes.py                 Hawkes arrivals (Phase 10)
│   │   ├── price.py                  Endogenous price, OU fit (Phase 11)
│   │   ├── maker.py                  Avellaneda-Stoikov maker (Phase 12)
│   │   ├── shocks.py                 News shock events (Phase 9)
│   │   ├── execution.py              TWAP, VWAP, participation, Almgren-Chriss (Phase 13)
│   │   ├── metrics.py                Herfindahl, effective holdings, correlation (Phases 14-15)
│   │   ├── validation.py             Stylized facts (Phase 18)
│   │   └── fast/                     Numba versions of hot loops (Phase 19)
│   ├── services/                     Business logic between UI and engine
│   │   ├── __init__.py
│   │   ├── auth.py                   Register, verify, login, lockout, sessions, reset, delete
│   │   ├── clock.py                  ISO 8601 UTC timestamp generation
│   │   ├── errors.py                 Domain exceptions and error codes
│   │   ├── runs.py                   Build configs, call engine, save and load runs
│   │   ├── catalog.py                Search, presets, comparison limit
│   │   ├── market.py                 Quotes and history with labels, caching
│   │   ├── news.py                   Headlines, demo and live modes
│   │   ├── analyst.py                Four prompts, demo answers, live calls
│   │   ├── chat.py                   Context, guardrails, tools, confirmations, limits
│   │   └── security.py               Password rules, token generation, hashing helpers
│   ├── adapters/                     Calls to the outside world. Each has a timeout and fallback.
│   │   ├── __init__.py
│   │   ├── market_yfinance.py
│   │   ├── market_twelvedata.py
│   │   ├── news_rss.py
│   │   ├── email_smtp.py
│   │   └── llm.py                    Provider wrapper
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py                     Connection, WAL, foreign keys, transactions
│   │   ├── migrate.py                Runs numbered SQL files
│   │   ├── repositories.py           All SQL queries, parameter-bound
│   │   └── migrations/
│   │       ├── 0001_init.sql         users, sessions, auth_tokens
│   │       ├── 0002_runs.sql         runs, schema_migrations
│   │       ├── 0003_watchlist.sql
│   │       ├── 0004_chat.sql         chat_messages, pending_actions
│   │       ├── 0005_catalog.sql      company_catalog
│   │       └── 0006_audit.sql        audit_log
│   ├── ui/
│   │   ├── app.py                    Entry point, page router, banner, chat button
│   │   ├── state.py                  Session state keys (one place)
│   │   ├── theme.py                  Colors, fonts, CSS
│   │   ├── pages/
│   │   │   ├── home.py
│   │   │   ├── auth_pages.py         Register, login, verify, forgot, reset
│   │   │   ├── tour.py
│   │   │   ├── universe_map.py
│   │   │   ├── simulator.py
│   │   │   ├── impact_lab.py
│   │   │   ├── profiles.py           Liquidity profiles and radar
│   │   │   ├── market_data.py        Quote, history, watchlist
│   │   │   ├── news_lab.py           News feed and shocks
│   │   │   ├── correlation.py        Overview, verdict, concentration vs count
│   │   │   ├── compare.py            Search, presets, detailed matrix
│   │   │   ├── cross_impact.py
│   │   │   ├── execution_lab.py
│   │   │   ├── analyst.py
│   │   │   ├── validation.py
│   │   │   ├── run_history.py
│   │   │   ├── profile_account.py    Name, email, password, delete account
│   │   │   └── summary.py
│   │   └── components/
│   │       ├── badge.py              Provenance and mode badges
│   │       ├── stat_card.py
│   │       ├── confirm_dialog.py
│   │       ├── chart_container.py    Scrollable chart wrapper with summary
│   │       └── chat_panel.py
│   └── llm/
│       ├── prompts/                  Prompt templates as text files
│       └── guardrails.py             Advice detection, forbidden content
├── data/
│   ├── catalog.csv                   The company catalog (about 190 rows)
│   ├── presets.json                  Six preset baskets
│   ├── profiles/                     Stock liquidity profiles (JSON)
│   ├── demo/
│   │   ├── headlines.json            Bundled demo headlines
│   │   ├── analyst_answers.json      Bundled demo analyst answers
│   │   └── chat_answers.json         Bundled demo chat answers
│   └── .gitkeep
├── results/                          Saved run JSON for local use (gitignored)
├── tests/
│   ├── conftest.py                   Shared fixtures, network blocker
│   ├── test_architecture.py          Import rule checks
│   ├── engine/
│   │   ├── test_book.py
│   │   ├── test_flow.py
│   │   ├── test_impact.py
│   │   └── test_metrics.py
│   ├── services/
│   │   ├── test_auth.py
│   │   ├── test_runs.py
│   │   ├── test_catalog.py
│   │   ├── test_analyst.py
│   │   └── test_chat.py
│   ├── storage/
│   │   └── test_migrations.py
│   ├── ui/
│   │   ├── test_provenance_labels.py AC-41
│   │   └── test_browser_flows.py     Playwright
│   └── fixtures/                     Recorded API responses (no live calls)
└── docs/                             This specification set
```

## Naming rules

- Modules and files: lowercase with underscores.
- Classes: CamelCase. Functions and variables: snake_case. Constants: UPPER_CASE.
- Test files: test_<module>.py, placed in a folder that mirrors the source.
- Migration files: four-digit number, underscore, short name.

## Where new code goes

| If you are adding... | Put it in... |
|---|---|
| Matching or order logic | engine/book.py or a new engine file |
| A calculation on results | engine/metrics.py or engine/impact.py |
| A rule about users or permissions | services/ |
| A new external data source | adapters/ |
| A new table | a new migration file, plus storage/repositories.py |
| A new screen | ui/pages/ and a route in ui/app.py |
| A reusable visual | ui/components/ |
