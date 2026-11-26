"""Seeded self-exciting Hawkes process arrival generator (T10.1, FR-21)."""

import math
import random
from dataclasses import dataclass

from opentrade.engine.profiles import EngineProvenance


@dataclass(frozen=True)
class HawkesResult:
    """Output of a Hawkes arrival simulation with burstiness diagnostics."""

    timestamps: tuple[float, ...]
    event_count: int
    fano_factor: float
    provenance: EngineProvenance


def simulate_hawkes_arrivals(
    horizon_seconds: float,
    baseline_rate: float,
    alpha: float,
    beta: float,
    seed: int,
    bin_width: float = 5.0,
) -> HawkesResult:
    """Simulate a 1D exponential Hawkes process using Ogata's thinning algorithm."""
    if baseline_rate <= 0 or beta <= 0 or alpha < 0 or alpha >= beta:
        raise ValueError("Require baseline_rate > 0, beta > 0, and 0 <= alpha < beta")

    rng = random.Random(seed)  # noqa: S311
    timestamps: list[float] = []
    t = 0.0
    excitation = 0.0

    while t < horizon_seconds:
        upper_bound = baseline_rate + excitation
        dt = rng.expovariate(upper_bound)
        t_next = t + dt
        if t_next >= horizon_seconds:
            break

        excitation *= math.exp(-beta * dt)
        current_intensity = baseline_rate + excitation
        if rng.random() * upper_bound <= current_intensity:
            timestamps.append(t_next)
            excitation += alpha
        t = t_next

    # Compute Fano factor (var / mean of bin counts) to measure burstiness (> 1 for Hawkes)
    num_bins = max(2, int(horizon_seconds / bin_width))
    counts = [0] * num_bins
    for ts in timestamps:
        idx = min(num_bins - 1, int(ts / bin_width))
        counts[idx] += 1

    mean_c = sum(counts) / num_bins
    var_c = sum((c - mean_c) ** 2 for c in counts) / max(1, num_bins - 1)
    fano = var_c / mean_c if mean_c > 0 else 1.0

    return HawkesResult(
        timestamps=tuple(timestamps),
        event_count=len(timestamps),
        fano_factor=fano,
        provenance=EngineProvenance.SYNTHETIC,
    )
