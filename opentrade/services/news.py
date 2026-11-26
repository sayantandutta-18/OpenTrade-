"""News headlines service with demo and live modes (T8.1)."""

import json
import math
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opentrade.adapters.news_rss import RssAdapterError, RssNewsAdapter
from opentrade.engine.book import OrderBook, Side
from opentrade.engine.impact import inject_market_order
from opentrade.engine.order_flow import generate_order_flow, seed_initial_book
from opentrade.engine.profiles import get_profile
from opentrade.engine.shocks import ShockEvent, run_shock_flow

DEMO_HEADLINES_PATH = Path("data/demo/headlines.json")


def format_relative_age(published_at: str, now: datetime | None = None) -> str:
    """Format an ISO-8601 timestamp into relative age such as '2h ago' (AC-30)."""
    ref = now or datetime.now(UTC)
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta_sec = max(0, int((ref - dt).total_seconds()))
    except ValueError:
        return "recent"

    if delta_sec < 3600:
        return f"{max(1, delta_sec // 60)}m ago"
    if delta_sec < 86400:
        return f"{delta_sec // 3600}h ago"
    return f"{delta_sec // 86400}d ago"


def _load_demo_headlines(
    symbols: list[str] | None,
    sector: str | None,
    demo_path: Path,
) -> list[dict[str, Any]]:
    """Load bundled demo headlines filtered by symbol or sector."""
    raw = json.loads(demo_path.read_text(encoding="utf-8"))
    sym_set = {s.strip().upper() for s in (symbols or []) if s.strip()}
    sec = sector.strip() if sector and sector.strip() else None

    items: list[dict[str, Any]] = []
    for entry in raw:
        entry_syms = [str(s).upper() for s in entry.get("symbols", [])]
        entry_sec = str(entry.get("sector", ""))
        if sec and entry_sec != sec:
            continue
        if sym_set and not sym_set.intersection(entry_syms):
            continue
        pub = str(entry["published_at"])
        items.append(
            {
                "title": str(entry["title"]),
                "source": str(entry["source"]),
                "url": str(entry.get("url", "")),
                "published_at": pub,
                "age": format_relative_age(pub),
                "summary": str(entry.get("summary", "")),
                "symbols": entry_syms,
                "sector": entry_sec,
                "label": "DEMO",
            }
        )
    return items


def get_news(
    symbols: list[str] | None = None,
    mode: str = "demo",
    feed_urls: tuple[str, ...] = (),
    adapter: RssNewsAdapter | None = None,
    sector: str | None = None,
    demo_path: Path = DEMO_HEADLINES_PATH,
) -> dict[str, Any]:
    """Return news headlines in DEMO (zero network) or LIVE mode with fallback (AC-30, AC-31)."""
    clean_mode = mode.strip().lower()
    if clean_mode != "live":
        return {
            "mode": "DEMO",
            "fallback_reason": None,
            "items": _load_demo_headlines(symbols, sector, demo_path),
        }

    if not feed_urls:
        return {
            "mode": "DEMO",
            "fallback_reason": "Live news is unavailable right now. Showing demo headlines.",
            "items": _load_demo_headlines(symbols, sector, demo_path),
        }

    rss = adapter or RssNewsAdapter()
    live_items: list[dict[str, Any]] = []
    sym_set = {s.strip().upper() for s in (symbols or []) if s.strip()}
    try:
        for url in feed_urls:
            for item in rss.fetch_feed(url):
                matched_syms = [
                    s for s in sym_set if s in item.title.upper() or s in item.summary.upper()
                ]
                if sym_set and not matched_syms:
                    continue
                live_items.append(
                    {
                        "title": item.title,
                        "source": item.source,
                        "url": item.url,
                        "published_at": item.published_at,
                        "age": format_relative_age(item.published_at),
                        "summary": item.summary,
                        "symbols": matched_syms,
                        "sector": sector or "",
                        "label": "REAL",
                    }
                )
        if live_items:
            return {"mode": "LIVE", "fallback_reason": None, "items": live_items}
    except (RssAdapterError, OSError):
        pass

    return {
        "mode": "DEMO",
        "fallback_reason": "Live news is unavailable right now. Showing demo headlines.",
        "items": _load_demo_headlines(symbols, sector, demo_path),
    }


def _mean_ci95(values: list[float]) -> tuple[float, list[float]]:
    """Compute sample mean and 95% confidence interval."""
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, [mean, mean]
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    margin = 1.96 * math.sqrt(var) / math.sqrt(n)
    return mean, [mean - margin, mean + margin]


def compare_calm_vs_news_slippage(
    profile_id: str = "synthetic_default",
    seed: int = 42,
    qty: int = 600,
    trials: int = 8,
) -> dict[str, Any]:
    """Compare calm-regime vs. news-shock slippage with 95% CI (T9.2, SYNTHETIC)."""
    profile = get_profile(profile_id)
    calm_vals: list[float] = []
    news_vals: list[float] = []

    for i in range(trials):
        s_i = seed + i
        b_calm = OrderBook()
        seed_initial_book(b_calm, profile, random.Random(s_i))  # noqa: S311
        generate_order_flow(b_calm, profile, seed=s_i, steps=20)
        inj_calm = inject_market_order(b_calm, Side.BUY, qty=qty, provenance=profile.provenance)
        calm_vals.append(inj_calm.slippage_bps)

        b_news = OrderBook()
        seed_initial_book(b_news, profile, random.Random(s_i))  # noqa: S311
        shock = ShockEvent(
            step=10,
            duration=10,
            arrival_multiplier=3.0,
            cancel_liquidity_frac=0.6,
            directional_side=Side.BUY,
            directional_qty=300,
        )
        run_shock_flow(b_news, profile, seed=s_i, steps=20, shocks=(shock,))
        inj_news = inject_market_order(b_news, Side.BUY, qty=qty, provenance=profile.provenance)
        news_vals.append(inj_news.slippage_bps)

    calm_mean, calm_ci = _mean_ci95(calm_vals)
    news_mean, news_ci = _mean_ci95(news_vals)
    return {
        "profile_id": profile.profile_id,
        "provenance": "SYNTHETIC",
        "trials": trials,
        "calm": {"mean_bps": round(calm_mean, 3), "ci95": [round(x, 3) for x in calm_ci]},
        "news": {"mean_bps": round(news_mean, 3), "ci95": [round(x, 3) for x in news_ci]},
    }
