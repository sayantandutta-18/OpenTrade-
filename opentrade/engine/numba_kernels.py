"""Optional Numba hot-loop kernels with identical pure-Python fallback (T19.1)."""

import math
from typing import Any

try:
    from numba import njit  # type: ignore[import-not-found]

    NUMBA_AVAILABLE = True
except ImportError:
    njit = None
    NUMBA_AVAILABLE = False


def vwap_from_arrays_py(prices: list[float], qtys: list[int]) -> float:
    """Compute volume-weighted average price in pure Python."""
    total_qty = 0
    total_notional = 0.0
    for p, q in zip(prices, qtys, strict=True):
        total_qty += q
        total_notional += p * q
    return total_notional / total_qty if total_qty > 0 else 0.0


def excess_kurtosis_py(returns: list[float]) -> float:
    """Compute excess kurtosis (fourth standardized moment minus 3) in pure Python."""
    n = len(returns)
    if n < 4:
        return 0.0
    mean = sum(returns) / n
    m2 = sum((r - mean) ** 2 for r in returns) / n
    if m2 <= 0.0:
        return 0.0
    m4 = sum((r - mean) ** 4 for r in returns) / n
    return (m4 / (m2 * m2)) - 3.0


def abs_autocorr_lag1_py(returns: list[float]) -> float:
    """Compute lag-1 autocorrelation of absolute returns in pure Python."""
    n = len(returns)
    if n < 3:
        return 0.0
    abs_r = [abs(r) for r in returns]
    mean = sum(abs_r) / n
    num = 0.0
    den = 0.0
    for i in range(n):
        diff = abs_r[i] - mean
        den += diff * diff
        if i > 0:
            num += (abs_r[i] - mean) * (abs_r[i - 1] - mean)
    return num / den if den > 0.0 else 0.0


if NUMBA_AVAILABLE and njit is not None:
    _vwap_nb: Any = njit(cache=True)(vwap_from_arrays_py)
    _kurt_nb: Any = njit(cache=True)(excess_kurtosis_py)
    _ac_nb: Any = njit(cache=True)(abs_autocorr_lag1_py)
else:
    _vwap_nb = vwap_from_arrays_py
    _kurt_nb = excess_kurtosis_py
    _ac_nb = abs_autocorr_lag1_py


def vwap_from_arrays(prices: list[float], qtys: list[int]) -> float:
    """Compute VWAP using Numba JIT if available, else identical pure Python."""
    return float(_vwap_nb(prices, qtys))


def excess_kurtosis(returns: list[float]) -> float:
    """Compute excess kurtosis using Numba JIT if available, else identical pure Python."""
    val = float(_kurt_nb(returns))
    return 0.0 if math.isnan(val) else val


def abs_autocorr_lag1(returns: list[float]) -> float:
    """Compute lag-1 abs-return autocorrelation using Numba if available, else pure Python."""
    val = float(_ac_nb(returns))
    return 0.0 if math.isnan(val) else val
