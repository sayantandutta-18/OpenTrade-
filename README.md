⚡ OpenTrade

Deterministic Limit Order Book & Market Microstructure Workbench

Simulate price-time priority order books, test execution algorithms, measure non-linear market impact, and explore cross-asset dynamics—offline-first and 100% reproducible.

Quickstart • Features • Architecture • Testing • Provenance

⚠️ Prototype. Not investment advice.
OpenTrade is an educational and quantitative research platform. Every number, chart, and AI-generated insight carries an explicit provenance label (REAL, CALIBRATED, or SYNTHETIC).

🎯 Why OpenTrade?

Understanding how large orders move markets requires seeing beneath top-of-book quotes. OpenTrade bridges the gap between textbook market microstructure theory and hands-on experimentation:

Zero External Keys Required: Launch immediately in Demo Mode (seed = 42) with calibrated liquidity profiles, synthetic order flow, and bundled market/news fixtures.

Bit-Identical Reproducibility: Every simulation produces a canonical 12-character SHA-256 fingerprint (RunConfig + seed + schema_version) so experiments can be audited and re-run identically.

Integer-Tick Precision: Built from the ground up with exact integer-tick pricing (price_ticks: int) and strict FIFO queue tracking—eliminating floating-point drift in order matching.

✨ What You Can Do with OpenTrade

Module

Capabilities & Research Tools

📊 Matching Engine & Order Book

Full price-time priority engine supporting LIMIT, MARKET, IOC, FOK, POST_ONLY, and STOP orders, iceberg display/hidden replenishment, lot-size enforcement, Self-Trade Prevention (CANCEL_NEWEST / CANCEL_OLDEST), and tagged queue-position tracking.

🌊 Stochastic Flow & Dynamics

Seeded Poisson arrivals, power-law placement distances, NOISE / MOMENTUM / INFORMED trader archetypes, self-exciting 1D Hawkes processes (Ogata's thinning), endogenous mid-price drift, scheduled liquidity shocks, and multi-book cross-impact.

📉 Impact Lab & Execution Algos

Single-order arrival-mid slippage, multi-size impact sweeps with OLS log-log power-law fitting (95% CI), temporary vs. permanent impact decay curves, and execution strategy benchmarking (TWAP, VWAP, POV, and Almgren–Chriss IS).

🏦 Avellaneda–Stoikov Market Maker

Inventory-aware reservation pricing and optimal spread quoting with exact decomposition of realized spread capture vs. inventory mark-to-market P&L.

🌍 Global Universe & Profiles

Interactive Universe Map across 195 global companies, curated sector/region presets, 6-company comparison basket, missing-value-safe factor radar scoring, and cross-asset correlation & effective holdings analytics.

📰 Market Data & News Lab

Resilient Twelve Data quotes/OHLCV and XXE/HTML-sanitized RSS news feeds with TTL caching, exponential-backoff retries, and paired Calm vs. News Slippage simulation comparisons.

🤖 Guardrailed AI Analyst & Chat

4-prompt AI Analyst (DEMO / LIVE), verified numeric narrative summaries (every figure cross-checked against saved results), read-only screen assistant, and streaming chatbot with citations, advice refusal guardrails, and TTL-confirmed actions.

🚀 Quickstart

1. Clone & Install

git clone <repository-url>
cd opentrade
python -m venv .venv

# Activate virtual environment:
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

pip install -e ".[dev]"


2. Configure Environment

Create your local .env file from the template:

cp .env.example .env


Variable

Required

Default

Purpose

OPENTRADE_SECRET_KEY

Yes

—

Cryptographic secret for session signing & CSRF tokens (min 32 chars)

OPENTRADE_ENV

No

development

Runtime mode (development, test, production)

OPENTRADE_DB_PATH

No

data/opentrade.db

Local SQLite database path (WAL mode + foreign keys enabled)

TWELVE_DATA_API_KEY

No

""

Optional API key for live quotes/OHLCV (uses demo fallback if omitted)

LLM_API_KEY

No

""

Optional API key for live AI Analyst & Chat (uses offline demo mode if omitted)

3. Launch the Workbench

streamlit run opentrade/ui/app.py


Open http://localhost:8501 in your browser and click Start in demo mode (seed = 42) to explore immediately—or register a local account to save, compare, and re-run simulations.

🏗️ Architecture

OpenTrade enforces strict one-way dependency boundaries verified automatically by tests/test_architecture.py:

┌─────────────────────────────────────────────────────────────────┐
│  opentrade/ui/          Streamlit Views, Centralized State & UI │
└────────────────────────────────┬────────────────────────────────┘
                                 │ calls services & config only
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  opentrade/services/    Auth, Runs, Universe, Analytics & AI    │
└──────────────┬─────────────────────────────────┬────────────────┘
               │                                 │
               ▼                                 ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│  opentrade/storage/          │   │  opentrade/adapters/         │
│  SQLite WAL, Migrations &    │   │  Twelve Data, RSS News,      │
│  Parameterized Repositories  │   │  Email & Guardrailed LLM     │
└──────────────────────────────┘   └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  opentrade/engine/      Pure LOB, Matching, Flow, Impact & MM   │
│  (100% Isolated: Python Stdlib + Optional Numba Fallback Only)  │
└─────────────────────────────────────────────────────────────────┘


Security & Engineering Highlights

Account & Session Security: Argon2id password hashing, sliding-window sessions, CSRF protection, 5-attempt brute-force lockout, IP rate limiting, secret log redaction, and strict per-user 404 ownership isolation.

AI & Feed Safety: Prompt-injection data isolation, investment-advice refusal guardrails, TTL-gated state actions, DOCTYPE/ENTITY XML guards, and zero unsafe_allow_html=True on external or user content.

Optional Acceleration: Stylized-fact validation and hot numerical loops include optional Numba @njit kernels with verified pure-Python parity.

🧪 Testing & Quality Gates

The entire test suite runs 100% offline with live network sockets blocked by default (tests/conftest.py).

# Run all 260 unit, property, contract, persistence, UI, accessibility & security tests
pytest -v

# Run linting, formatting, and static type checks
ruff check .
black --check .
mypy opentrade tests


Optional Offline Profile Calibration

To recalibrate data/calibrated_profiles.json from historical market data outside of automated tests:

python scripts/calibrate_profiles.py


🏷️ Provenance & Disclaimer

Every metric, visualization, and generated sentence in OpenTrade displays its exact data origin:

🟢 REAL — Live or historical quotes, OHLCV bars, and RSS headlines retrieved from configured providers with source and timestamp metadata.

🟡 CALIBRATED — Microstructure parameters fitted from historical market statistics (spread, depth, and volatility regimes).

🔵 SYNTHETIC / DEMO — Outputs generated deterministically by OpenTrade's order book, stochastic flow, impact models, or bundled offline fixtures.

OpenTrade is built strictly for research, education, and software engineering demonstration. Nothing produced by this software constitutes financial or investment advice.
