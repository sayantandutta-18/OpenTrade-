"""Tests for historical replay mode (T20.3).

Follows docs/TASKS.md (T20.3) and docs/SRS.md (FR-52).
"""

from opentrade.services.replay import replay_historical_bars


def test_historical_replay_replays_bars_with_explicit_provenance_t20_3() -> None:
    """T20.3, FR-52: Replays historical OHLCV bars through order book with provenance labels."""
    bars = [
        {
            "date": "2026-01-12",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 500000,
        },
        {
            "date": "2026-01-13",
            "open": 100.5,
            "high": 102.0,
            "low": 100.0,
            "close": 101.8,
            "volume": 650000,
        },
        {
            "date": "2026-01-14",
            "open": 101.8,
            "high": 103.0,
            "low": 101.2,
            "close": 102.4,
            "volume": 720000,
        },
    ]
    replay = replay_historical_bars("AAPL", bars=bars, qty=200, bar_label="REAL")
    assert replay["symbol"] == "AAPL"
    assert replay["bar_label"] == "REAL"
    assert replay["simulation_label"] == "CALIBRATED"
    assert len(replay["steps"]) == 3
    assert all(step["filled_qty"] == 200 for step in replay["steps"])
    assert all(step["slippage_bps"] > 0.0 for step in replay["steps"])
