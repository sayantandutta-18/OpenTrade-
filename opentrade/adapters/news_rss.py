"""Safe RSS/Atom news adapter with 5s timeout, XXE guard, HTML strip, and 15-min cache (T8.1)."""

import html
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

DEFAULT_TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 900.0  # 15 minutes per docs/TRD.md §5
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


class RssAdapterError(RuntimeError):
    """Raised when fetching or safely parsing an RSS/Atom feed fails."""


@dataclass(frozen=True)
class RssHeadline:
    """Sanitized news headline parsed from an RSS or Atom feed."""

    title: str
    source: str
    url: str
    published_at: str
    summary: str


TransportFn = Callable[[str, float], tuple[int, str]]


def _urllib_transport(url: str, timeout: float) -> tuple[int, str]:
    """Default HTTP GET transport using stdlib urllib with explicit timeout."""
    if not url.startswith(("http://", "https://")):
        raise RssAdapterError("Unsupported URL scheme")
    req = urllib.request.Request(url, headers={"User-Agent": "OpenTrade/1.0"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def sanitize_feed_text(raw: str) -> str:
    """Strip script/style blocks and HTML tags, unescaping entities safely."""
    unescaped = html.unescape(raw or "")
    no_scripts = _SCRIPT_STYLE_RE.sub("", unescaped)
    stripped = _HTML_TAG_RE.sub("", no_scripts)
    return " ".join(stripped.split())


def _normalize_timestamp(raw_ts: str) -> str:
    """Normalize RFC-2822 or ISO-8601 feed timestamps to ISO-8601 UTC."""
    text = (raw_ts or "").strip()
    if not text:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return text


def parse_rss_xml(xml_text: str, default_source: str = "RSS Feed") -> list[RssHeadline]:
    """Safely parse RSS 2.0 or Atom XML, rejecting DOCTYPE/ENTITY declarations."""
    upper = xml_text.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise RssAdapterError("Rejected XML feed containing DOCTYPE or ENTITY declarations")

    try:
        root = ET.fromstring(xml_text)  # noqa: S314
    except ET.ParseError as exc:
        raise RssAdapterError("Malformed RSS XML feed") from exc

    headlines: list[RssHeadline] = []
    channel = root.find("channel")
    if channel is not None:
        feed_source = sanitize_feed_text(channel.findtext("title") or default_source)
        for item in channel.findall("item"):
            title = sanitize_feed_text(item.findtext("title") or "")
            if not title:
                continue
            url = (item.findtext("link") or "").strip()
            pub = _normalize_timestamp(item.findtext("pubDate") or "")
            summary = sanitize_feed_text(item.findtext("description") or "")
            headlines.append(
                RssHeadline(
                    title=title,
                    source=feed_source or default_source,
                    url=url,
                    published_at=pub,
                    summary=summary,
                )
            )
        return headlines

    # Atom fallback (<feed><entry>)
    ns = "{http://www.w3.org/2005/Atom}"
    feed_source = sanitize_feed_text(root.findtext(f"{ns}title") or default_source)
    for entry in root.findall(f"{ns}entry"):
        title = sanitize_feed_text(entry.findtext(f"{ns}title") or "")
        if not title:
            continue
        link_el = entry.find(f"{ns}link")
        url = (link_el.attrib.get("href", "") if link_el is not None else "").strip()
        pub = _normalize_timestamp(
            entry.findtext(f"{ns}updated") or entry.findtext(f"{ns}published") or ""
        )
        summary = sanitize_feed_text(entry.findtext(f"{ns}summary") or "")
        headlines.append(
            RssHeadline(
                title=title,
                source=feed_source or default_source,
                url=url,
                published_at=pub,
                summary=summary,
            )
        )
    return headlines


class RssNewsAdapter:
    """RSS news adapter with 5s timeout and 15-minute TTL cache per feed URL."""

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        cache_ttl_seconds: float = CACHE_TTL_SECONDS,
        transport: TransportFn | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._ttl = cache_ttl_seconds
        self._transport = transport or _urllib_transport
        self._clock = clock or time.monotonic
        self._cache: dict[str, tuple[float, list[RssHeadline]]] = {}

    def fetch_feed(self, feed_url: str) -> list[RssHeadline]:
        """Fetch and parse RSS feed URL with 15-min cache."""
        now = self._clock()
        cached = self._cache.get(feed_url)
        if cached is not None and (now - cached[0]) < self._ttl:
            return cached[1]

        try:
            status, body = self._transport(feed_url, self._timeout)
        except Exception as exc:
            raise RssAdapterError(f"RSS fetch failed: {type(exc).__name__}") from exc

        if status != 200:
            raise RssAdapterError(f"RSS feed returned HTTP {status}")

        items = parse_rss_xml(body)
        self._cache[feed_url] = (now, items)
        return items
