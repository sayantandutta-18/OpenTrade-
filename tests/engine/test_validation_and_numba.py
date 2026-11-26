"""Tests for stylized-fact validation (T18.1) and Numba hot-loop parity (T19.1).

Follows docs/TASKS.md (T18.1, T19.1) and docs/TRD.md (§4 performance targets).
"""

import time

from opentrade.engine.numba_kernels import (
    NUMBA_AVAILABLE,
    abs_autocorr_lag1,
    abs_autocorr_lag1_py,
    excess_kurtosis,
    excess_kurtosis_py,
    vwap_from_arrays,
    vwap_from_arrays_py,
)
from opentrade.engine.profiles import EngineProvenance
from opentrade.engine.validation import run_stylized_fact_validation


def test_stylized_fact_validation_checks_pass_with_synthetic_provenance_t18_1() -> None:
    """T18.1, FR-52: Stylized-fact checks return PASS/FAIL per fact with SYNTHETIC label."""
    res = run_stylized_fact_validation(profile_id="high_volatility", seed=42, steps=250)
    assert len(res.checks) == 4
    names = {c.name for c in res.checks}
    assert names == {"fat_tails", "volatility_clustering", "positive_spread", "signature_plot"}
    assert all(c.provenance is EngineProvenance.SYNTHETIC for c in res.checks)
    assert res.provenance is EngineProvenance.SYNTHETIC
    assert res.all_passed is True


def test_numba_kernels_match_pure_python_and_meet_speed_target_t19_1() -> None:
    """T19.1, TRD §4: Optional Numba kernels match pure Python within 1e-12 and run fast."""
    _ = NUMBA_AVAILABLE
    prices = [100.0 + (i % 7) * 0.25 for i in range(10_000)]
    qtys = [10 + (i % 5) * 5 for i in range(10_000)]
    returns = [((i % 9) - 4) * 0.002 + (0.015 if i % 40 == 0 else 0.0) for i in range(5_000)]

    assert abs(vwap_from_arrays(prices, qtys) - vwap_from_arrays_py(prices, qtys)) < 1e-12
    assert abs(excess_kurtosis(returns) - excess_kurtosis_py(returns)) < 1e-12
    assert abs(abs_autocorr_lag1(returns) - abs_autocorr_lag1_py(returns)) < 1e-12

    t0 = time.perf_counter()
    vwap_from_arrays(prices, qtys)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 200.0
