"""Offline CLI utility to calibrate liquidity profiles from yfinance OHLCV bars (T6.1)."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from opentrade.services.profiles import (
    CALIBRATED_PROFILES_PATH,
    calibrate_profile_from_bars,
)


def main() -> None:
    """Fetch historical bars via yfinance (offline CLI only) and update calibrated JSON."""
    parser = argparse.ArgumentParser(description="Calibrate OpenTrade liquidity profiles")
    parser.add_argument("--symbols", nargs="+", default=["AAPL", "MSFT", "NVDA", "JPM", "TSLA"])
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--out", type=Path, default=CALIBRATED_PROFILES_PATH)
    args = parser.parse_args()

    import yfinance as yf  # type: ignore[import-untyped]

    calibrated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = []
    for sym in args.symbols:
        hist = yf.Ticker(sym).history(period=f"{args.days}d")
        bars = [
            {
                "close": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "volume": float(row["Volume"]),
            }
            for _, row in hist.iterrows()
        ]
        prof = calibrate_profile_from_bars(sym, bars, calibrated_at=calibrated_at)
        entries.append(
            {
                "symbol": prof.symbol,
                "tick_size": prof.tick_size,
                "typical_spread_bps": prof.typical_spread_bps,
                "top_depth_shares": prof.top_depth_shares,
                "arrival_rate_per_sec": prof.arrival_rate_per_sec,
                "daily_volatility": prof.daily_volatility,
                "source": prof.source,
                "calibrated_at": prof.calibrated_at,
                "provenance": prof.provenance.value,
                "raw_metrics": prof.raw_metrics,
            }
        )

    args.out.write_text(
        json.dumps({"schema_version": 1, "profiles": entries}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
