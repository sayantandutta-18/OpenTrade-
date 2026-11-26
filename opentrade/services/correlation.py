"""Portfolio correlation matrix, diversification verdict, and effective holdings (T14.1)."""

import math
from typing import Any

from opentrade.services.market import MarketDataAdapter, get_history


def diversification_verdict(avg_correlation: float) -> str:
    """Return diversification verdict per AC-32 (<0.3 well diversified, 0.3-0.6 moderate, >0.6)."""
    if avg_correlation < 0.3:
        return "well diversified"
    if avg_correlation <= 0.6:
        return "moderate"
    return "concentrated"


def effective_holdings(weights: list[float]) -> float:
    """Compute effective independent holdings = 1 / sum(w_i^2) per AC-33 and FR-43."""
    if not weights:
        raise ValueError("weights cannot be empty")
    total = sum(weights)
    if total <= 0:
        raise ValueError("sum of weights must be positive")
    norm = [w / total for w in weights]
    hhi = sum(w * w for w in norm)
    return 1.0 / hhi if hhi > 0 else 0.0


def concentration_vs_count_curve(
    max_n: int = 20,
    avg_corr: float = 0.25,
) -> list[dict[str, float | int]]:
    """Compute effective independent bets vs. nominal equal-weighted holding count N."""
    curve: list[dict[str, float | int]] = []
    rho = max(-0.99, min(0.99, avg_corr))
    for n in range(1, max_n + 1):
        # Under equal weights and uniform correlation rho, portfolio variance scales as
        # (1/N) + ((N-1)/N)*rho => effective independent holdings = 1 / ((1/N) + ((N-1)/N)*rho)
        eff = n / (1.0 + (n - 1) * max(0.0, rho))
        curve.append(
            {
                "nominal_n": n,
                "effective_n": round(eff, 3),
                "hhi": round(1.0 / n, 4),
            }
        )
    return curve


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    xs_c, ys_c = xs[:n], ys[:n]
    mx = sum(xs_c) / n
    my = sum(ys_c) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs_c, ys_c, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs_c))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys_c))
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0


def analyze_correlation(
    symbols: list[str],
    weights: list[float] | None = None,
    days: int = 60,
    adapter: MarketDataAdapter | None = None,
) -> dict[str, Any]:
    """Compute return correlation matrix, verdict, and effective holdings (AC-32, AC-33)."""
    clean_syms = [s.strip().upper() for s in symbols if s.strip()]
    if not clean_syms:
        raise ValueError("At least one symbol is required")

    resolved_weights = weights if weights is not None else [1.0 / len(clean_syms)] * len(clean_syms)
    eff_n = effective_holdings(resolved_weights)

    returns_by_sym: dict[str, list[float]] = {}
    labels: set[str] = set()
    for sym in clean_syms:
        hist = get_history(sym, days=days, adapter=adapter)
        labels.add(str(hist["label"]))
        closes = [float(pt["close"]) for pt in hist["points"]]
        rets = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        returns_by_sym[sym] = rets

    label = "REAL" if labels == {"REAL"} else "SIMULATED"
    matrix: list[list[float]] = []
    pair_corrs: list[float] = []
    for i, s1 in enumerate(clean_syms):
        row: list[float] = []
        for j, s2 in enumerate(clean_syms):
            corr = 1.0 if i == j else round(_pearson(returns_by_sym[s1], returns_by_sym[s2]), 4)
            row.append(corr)
            if j > i:
                pair_corrs.append(corr)
        matrix.append(row)

    avg_corr = sum(pair_corrs) / len(pair_corrs) if pair_corrs else 0.0
    verdict = diversification_verdict(avg_corr)
    return {
        "symbols": clean_syms,
        "matrix": matrix,
        "avg_correlation": round(avg_corr, 4),
        "verdict": verdict,
        "effective_holdings": round(eff_n, 4),
        "nominal_holdings": len(clean_syms),
        "concentration_curve": concentration_vs_count_curve(max_n=12, avg_corr=avg_corr),
        "label": label,
    }
