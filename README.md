# OpenTrade

OpenTrade is a web application for exploring how financial markets absorb large orders. A user selects stocks, runs a simulated limit order book, injects a trade of a chosen size, and observes how much the price moves.

Every number shown carries an explicit provenance label: **REAL**, **CALIBRATED**, or **SYNTHETIC**. Simulated data is never shown as real.

## Setup

Requirements: Python 3.11 or later.

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env       # Windows: copy .env.example .env
# Edit .env to set a secret key (minimum 32 characters)

# Run migrations
python -m opentrade.storage.migrate

# Run tests
pytest

# Launch the app
streamlit run opentrade/ui/app.py
```

## Documentation

Full specifications are located in the `docs/` directory. See `docs/README.md` for the document index and `docs/AGENTS.md` for coding agent guidelines.
