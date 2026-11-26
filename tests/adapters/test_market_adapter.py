"""Contract tests for market data adapter (T7.1).

Follows docs/TRD.md (§2.4, §5) and docs/ACCEPTANCE_CRITERIA.md (AC-28).
"""

import json
from typing import Any

import pytest

from opentrade.adapters.market_twelvedata import (
    AdapterError,
    TwelveDataAdapter,
)


def test_twelvedata_quote_parses_fixture_and_caches_15_minutes() -> None:
    """T7.1, TRD §5: Quote adapter parses JSON fixture and serves cached result within 15 min."""
    calls: list[tuple[str, float]] = []
    now = [1000.0]

    def mock_transport(url: str, timeout: float) -> tuple[int, str]:
        calls.append((url, timeout))
        return 200, json.dumps(
            {
                "symbol": "AAPL",
                "close": "195.50",
                "open": "193.00",
                "previous_close": "192.50",
                "high": "196.20",
                "low": "192.10",
                "change": "3.00",
                "percent_change": "1.558",
                "datetime": "2026-01-15",
            }
        )

    adapter = TwelveDataAdapter(
        api_key="test-key-never-logged",
        transport=mock_transport,
        clock=lambda: now[0],
        sleep_fn=lambda _: None,
    )
    q1 = adapter.fetch_quote("AAPL")
    assert q1.symbol == "AAPL"
    assert q1.price == 195.50
    assert q1.source == "twelvedata"
    assert len(calls) == 1
    assert calls[0][1] == 5.0  # 5-second timeout per TRD §2.4

    # Within 15 minutes (900s), cache hit avoids transport call
    now[0] += 300.0
    q2 = adapter.fetch_quote("AAPL")
    assert q2 == q1
    assert len(calls) == 1

    # After 15 minutes (900s), cache expires and refetches
    now[0] += 700.0
    adapter.fetch_quote("AAPL")
    assert len(calls) == 2


def test_twelvedata_retries_up_to_two_times_with_backoff_then_raises() -> None:
    """T7.1, TRD §2.4: Adapter retries transient failures up to 2 times with backoff."""
    attempts = [0]
    sleeps: list[float] = []

    def failing_transport(url: str, timeout: float) -> tuple[int, str]:
        attempts[0] += 1
        raise TimeoutError("timed out")

    adapter = TwelveDataAdapter(
        api_key="secret-td-key",
        transport=failing_transport,
        sleep_fn=lambda sec: sleeps.append(sec),
    )
    with pytest.raises(AdapterError) as exc_info:
        adapter.fetch_quote("AAPL")

    assert attempts[0] == 3  # 1 initial + 2 retries
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0]
    # Never leak API key in error text
    assert "secret-td-key" not in str(exc_info.value)


def test_twelvedata_history_parses_ohlcv_bars() -> None:
    """T7.1: History adapter parses time_series JSON fixture into OHLCV bars."""

    def mock_transport(url: str, timeout: float) -> tuple[int, str]:
        return 200, json.dumps(
            {
                "meta": {"symbol": "MSFT"},
                "values": [
                    {
                        "datetime": "2026-01-15",
                        "open": "410.0",
                        "high": "415.0",
                        "low": "408.0",
                        "close": "414.0",
                        "volume": "1200000",
                    },
                    {
                        "datetime": "2026-01-14",
                        "open": "405.0",
                        "high": "411.0",
                        "low": "404.0",
                        "close": "410.0",
                        "volume": "1000000",
                    },
                ],
            }
        )

    adapter: Any = TwelveDataAdapter(
        api_key="test-key",
        transport=mock_transport,
        sleep_fn=lambda _: None,
    )
    bars = adapter.fetch_history("MSFT", days=60)
    assert len(bars) == 2
    assert bars[0].date == "2026-01-14"  # Chronological ascending
    assert bars[1].close == 414.0
