"""Tests for RSS news adapter and demo/live news service (T8.1).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-30, AC-31), docs/SRS.md (FR-39, FR-40, FR-52),
and docs/CODING_STANDARDS.md (§7).
"""

from datetime import UTC, datetime

import pytest

from opentrade.adapters.news_rss import RssAdapterError, RssNewsAdapter
from opentrade.services.news import format_relative_age, get_news

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>MarketWire</title>
    <item>
      <title>&lt;b&gt;AAPL&lt;/b&gt; expands silicon roadmap</title>
      <link>https://example.com/aapl-silicon</link>
      <pubDate>Thu, 15 Jan 2026 14:00:00 GMT</pubDate>
      <description>&lt;script&gt;alert(1)&lt;/script&gt;Apple announces new chips.</description>
    </item>
  </channel>
</rss>
"""


def test_rss_adapter_parses_sanitizes_html_and_caches_15_min() -> None:
    """T8.1, AC-30, CODING_STANDARDS §7: Parses RSS, strips HTML tags, caches 15 minutes."""
    calls: list[str] = []
    now = [100.0]

    def mock_transport(url: str, timeout: float) -> tuple[int, str]:
        calls.append(url)
        assert timeout == 5.0
        return 200, SAMPLE_RSS

    adapter = RssNewsAdapter(transport=mock_transport, clock=lambda: now[0])
    items = adapter.fetch_feed("https://feeds.example.com/markets.rss")
    assert len(items) == 1
    assert items[0].title == "AAPL expands silicon roadmap"
    assert "<b>" not in items[0].title
    assert "<script>" not in items[0].summary
    assert items[0].source == "MarketWire"
    assert items[0].published_at

    # Within 15 min, served from cache
    now[0] += 400.0
    adapter.fetch_feed("https://feeds.example.com/markets.rss")
    assert len(calls) == 1


def test_rss_adapter_rejects_xxe_doctype_entities() -> None:
    """T8.1, CODING_STANDARDS §7: Rejects XML payloads containing DOCTYPE or ENTITY."""
    xxe_xml = """<?xml version="1.0"?>
    <!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
    <rss><channel><item><title>&xxe;</title></item></channel></rss>
    """
    adapter = RssNewsAdapter(transport=lambda url, t: (200, xxe_xml))
    with pytest.raises(RssAdapterError):
        adapter.fetch_feed("https://feeds.example.com/evil.rss")


def test_demo_news_makes_zero_network_calls_ac31() -> None:
    """T8.1, AC-30, AC-31: Demo news mode uses bundled headlines with zero HTTP calls."""
    # tests/conftest.py already blocks socket.connect globally; any HTTP call raises RuntimeError
    res = get_news(symbols=["AAPL", "JPM"], mode="demo")
    assert res["mode"] == "DEMO"
    assert len(res["items"]) >= 2
    for item in res["items"]:
        assert item["source"]
        assert item["published_at"]
        assert item["label"] == "DEMO"


def test_live_news_falls_back_to_demo_on_feed_failure() -> None:
    """T8.1, FR-40, USER_FLOW Flow 7: Failing live RSS falls back to DEMO headlines with notice."""
    failing_adapter = RssNewsAdapter(transport=lambda url, t: (503, "Service Unavailable"))
    res = get_news(
        symbols=["AAPL"],
        mode="live",
        feed_urls=("https://feeds.example.com/down.rss",),
        adapter=failing_adapter,
    )
    assert res["mode"] == "DEMO"
    assert "unavailable" in str(res["fallback_reason"]).lower()
    assert all(item["label"] == "DEMO" for item in res["items"])


def test_format_relative_age_ac30() -> None:
    """AC-30: Relative age formats as '2h ago', '15m ago', '3d ago'."""
    now = datetime(2026, 1, 15, 16, 0, 0, tzinfo=UTC)
    assert format_relative_age("2026-01-15T14:00:00Z", now=now) == "2h ago"
    assert format_relative_age("2026-01-15T15:45:00Z", now=now) == "15m ago"
    assert format_relative_age("2026-01-12T16:00:00Z", now=now) == "3d ago"
