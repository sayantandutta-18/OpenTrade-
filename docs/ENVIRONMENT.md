# Environment

Version: 1.0

## 1. Variables

The app reads these from environment variables (or .env in local development). It validates them at startup and refuses to start if a required value is missing or malformed.

| Name | Required | Default | Example | Purpose |
|---|---|---|---|---|
| OPENTRADE_ENV | Yes | none | local | local, staging, or production. Controls cookie flags, logging, and email behavior |
| OPENTRADE_SECRET_KEY | Yes | none | 64 random characters | Signs CSRF tokens and hashes IP addresses. Must be at least 32 characters |
| OPENTRADE_DB_PATH | No | ./data/opentrade.db | /data/opentrade.db | SQLite file path |
| OPENTRADE_BASE_URL | Yes | none | http://localhost:8501 | Used to build links in emails |
| OPENTRADE_LOG_LEVEL | No | INFO | DEBUG | Log level |
| OPENTRADE_CHAT_HOURLY_LIMIT | No | 30 | 30 | Chat messages per user per hour |
| OPENTRADE_CHAT_DAILY_LIMIT | No | 50 | 50 | Chat messages per user per day |
| OPENTRADE_ANALYST_DAILY_LIMIT | No | 20 | 20 | Live analyst calls per user per day |
| OPENTRADE_RUN_DAILY_LIMIT | No | 100 | 100 | Saved runs per user per day |
| OPENTRADE_ALLOW_LIVE_DATA | No | false | true | Master switch for live market and news calls |
| SMTP_HOST | Yes in staging and production | none | smtp.example.com | Email server |
| SMTP_PORT | No | 587 | 587 | Email port (STARTTLS) |
| SMTP_USER | Yes in staging and production | none | apikey | Email login |
| SMTP_PASSWORD | Yes in staging and production | none | (secret) | Email password. Never logged |
| SMTP_FROM | Yes in staging and production | none | OpenTrade <no-reply@example.com> | Sender address |
| MARKET_PROVIDER | No | yfinance | yfinance or twelvedata | Quote and history source |
| TWELVE_DATA_API_KEY | No | none | (secret) | Needed only if MARKET_PROVIDER is twelvedata |
| NEWS_FEEDS | No | built-in list | comma-separated RSS URLs | News sources |
| LLM_PROVIDER | No | none | (provider name) | Empty means demo-only analyst and chat |
| LLM_API_KEY | No | none | (secret) | LLM key. Never logged |
| LLM_MODEL | No | provider default | (model name) | Model for analyst and chat |

Rules:
- Any variable marked secret is read from the environment only and never printed, logged, or returned by the API.
- If LLM_PROVIDER is empty, the analyst and chat run in demo mode. The app still starts.
- If OPENTRADE_ALLOW_LIVE_DATA is false, live calls are never made, even if keys are set.

## 2. .env.example

```
OPENTRADE_ENV=local
OPENTRADE_SECRET_KEY=replace-with-64-random-characters-minimum-32
OPENTRADE_DB_PATH=./data/opentrade.db
OPENTRADE_BASE_URL=http://localhost:8501
OPENTRADE_LOG_LEVEL=INFO
OPENTRADE_ALLOW_LIVE_DATA=false
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
MARKET_PROVIDER=yfinance
TWELVE_DATA_API_KEY=
NEWS_FEEDS=
LLM_PROVIDER=
LLM_API_KEY=
LLM_MODEL=
```

## 3. Local setup

Requirements: Python 3.11 or later, Git, a modern browser.

```
git clone <repo-url> opentrade
cd opentrade
python -m venv .venv
source .venv/bin/activate          (Windows: .venv\Scripts\activate)
pip install -e ".[dev]"
cp .env.example .env               (Windows: copy .env.example .env)
# Edit .env: set OPENTRADE_SECRET_KEY to a random value
python -m opentrade.storage.migrate
python -m pytest
streamlit run opentrade/ui/app.py
```

In local mode, verification and reset emails are printed to the terminal instead of sent. This is controlled by OPENTRADE_ENV=local.

## 4. Dependencies

Declared in pyproject.toml. Minimum set for Phase 0:
- streamlit
- argon2-cffi
- pandas
- numpy
- python-dotenv
- pytest, hypothesis, ruff, black, mypy (dev extras)

Added later with a DECISIONS.md entry: yfinance (Phase 4), feedparser (Phase 8), numba (Phase 19), playwright (Phase 0 dev extras for browser tests), LLM SDK (Phase 16).

## 5. Ports and paths

- Streamlit: port 8501.
- Database: OPENTRADE_DB_PATH.
- Logs: standard output (JSON lines). No log files written by the app itself.
