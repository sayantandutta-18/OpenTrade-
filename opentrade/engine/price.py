"""Endogenous mid-price evolution driven by signed order imbalance (T11.1)."""


def evolve_endogenous_mid(
    initial_mid_ticks: int,
    signed_imbalances: list[int],
    sensitivity: float = 0.01,
) -> list[int]:
    """Evolve integer-tick mid price from cumulative signed order imbalance."""
    if initial_mid_ticks <= 0:
        raise ValueError("initial_mid_ticks must be positive")

    mid_float = float(initial_mid_ticks)
    path: list[int] = [initial_mid_ticks]
    for imb in signed_imbalances:
        mid_float = max(1.0, mid_float + sensitivity * imb)
        path.append(max(1, round(mid_float)))
    return path
