"""Market data adapter using Twelve Data with timeout, retry, and 15-min TTL cache (T7.1)."""

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_RETRIES = 2
CACHE_TTL_SECONDS = 900.0  # 15 minutes per docs/TRD.md §5


class AdapterError(RuntimeError):
    """Raised when an external adapter fails after retries."""


@dataclass(frozen=True)
class QuoteData:
    """Normalized market quote payload."""

    symbol: str
    price: float
    change: float
    change_pct: float
    open: float
    prev_close: float
    high: float
    low: float
    source: str
    as_of: str


@dataclass(frozen=True)
class HistoryBar:
    """Single OHLCV daily bar."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


TransportFn = Callable[[str, float], tuple[int, str]]


def _urllib_transport(url: str, timeout: float) -> tuple[int, str]:
    """Default HTTP GET transport using stdlib urllib with explicit timeout."""
    if not url.startswith(("http://", "https://")):
        raise AdapterError("Unsupported URL scheme")
    req = urllib.request.Request(url, headers={"User-Agent": "OpenTrade/1.0"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return int(resp.status), resp.read().decode("utf-8")


class TwelveDataAdapter:
    """Twelve Data REST adapter with 5s timeout, 2 retries with backoff, and 15-min cache."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        cache_ttl_seconds: float = CACHE_TTL_SECONDS,
        transport: TransportFn | None = None,
        clock: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._ttl = cache_ttl_seconds
        self._transport = transport or _urllib_transport
        self._clock = clock or time.monotonic
        self._sleep = sleep_fn or time.sleep
        self._quote_cache: dict[tuple[str, str], tuple[float, QuoteData]] = {}
        self._history_cache: dict[tuple[str, int, str], tuple[float, list[HistoryBar]]] = {}

    def _today_key(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _request_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        """Perform HTTP GET with bounded retries and exponential backoff; never leak API key."""
        if not self._api_key:
            raise AdapterError("TWELVE_DATA_API_KEY is not configured")

        full_params = {**params, "apikey": self._api_key}
        url = f"https://api.twelvedata.com/{path}?{urllib.parse.urlencode(full_params)}"

        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                status, body = self._transport(url, self._timeout)
                if status != 200:
                    raise AdapterError(f"Twelve Data HTTP {status}")
                payload = json.loads(body)
                if not isinstance(payload, dict) or payload.get("status") == "error":
                    raise AdapterError("Twelve Data returned an error payload")
                return payload
            except Exception as exc:
                last_err = exc
                if attempt < self._max_retries:
                    self._sleep(0.25 * (2**attempt))

        raise AdapterError(f"Twelve Data request failed after retries: {type(last_err).__name__}")

    def fetch_quote(self, symbol: str) -> QuoteData:
        """Fetch latest quote for `symbol`, using 15-min cache keyed by (symbol, date)."""
        clean = symbol.strip().upper()
        cache_key = (clean, self._today_key())
        now = self._clock()
        cached = self._quote_cache.get(cache_key)
        if cached is not None and (now - cached[0]) < self._ttl:
            return cached[1]

        data = self._request_json("quote", {"symbol": clean})
        try:
            quote = QuoteData(
                symbol=clean,
                price=float(data["close"]),
                change=float(data.get("change", 0.0)),
                change_pct=float(data.get("percent_change", 0.0)),
                open=float(data.get("open", data["close"])),
                prev_close=float(data.get("previous_close", data["close"])),
                high=float(data.get("high", data["close"])),
                low=float(data.get("low", data["close"])),
                source="twelvedata",
                as_of=str(data.get("datetime") or self._today_key()),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError("Malformed quote payload from Twelve Data") from exc

        self._quote_cache[cache_key] = (now, quote)
        return quote

    def fetch_history(self, symbol: str, days: int = 60) -> list[HistoryBar]:
        """Fetch daily OHLCV bars in chronological ascending order."""
        clean = symbol.strip().upper()
        cache_key = (clean, days, self._today_key())
        now = self._clock()
        cached = self._history_cache.get(cache_key)
        if cached is not None and (now - cached[0]) < self._ttl:
            return cached[1]

        data = self._request_json(
            "time_series",
            {"symbol": clean, "interval": "1day", "outputsize": str(days)},
        )
        values = data.get("values")
        if not isinstance(values, list) or not values:
            raise AdapterError("Empty time_series values from Twelve Data")

        bars: list[HistoryBar] = []
        for item in values:
            bars.append(
                HistoryBar(
                    date=str(item["datetime"]),
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=int(float(item.get("volume", 0))),
                )
            )
        bars.sort(key=lambda b: b.date)
        self._history_cache[cache_key] = (now, bars)
        return bars
