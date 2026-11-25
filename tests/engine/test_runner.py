"""Tests for multi-size/multi-strategy simulation runner & determinism (T1.8-T1.9).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-16, AC-21), docs/SRS.md (FR-15, FR-27, FR-52).
"""

import json

from opentrade.config import RunConfig, compute_fingerprint
from opentrade.engine.impact import ExecutionStrategy
from opentrade.engine.profiles import EngineProvenance
from opentrade.engine.runner import run_simulation


def test_simulation_runner_executes_sizes_and_strategies_t1_8() -> None:
    """FR-27, FR-52: Runner executes all configured sizes and strategies with provenance."""
    cfg = RunConfig(seed=42, profile_id="deep_book", sizes=(100, 500, 1000), book_depth=15)
    result = run_simulation(
        seed=cfg.seed,
        profile_id=cfg.profile_id,
        sizes=cfg.sizes,
        book_depth=cfg.book_depth,
        strategies=(ExecutionStrategy.TWAP, ExecutionStrategy.IS),
    )

    assert result.seed == 42
    assert result.profile_id == "deep_book"
    assert result.provenance is EngineProvenance.CALIBRATED
    assert len(result.points) == 6  # 3 sizes x 2 strategies
    assert result.to_dict()["provenance"] == "CALIBRATED"


def test_simulation_runner_reproducibility_and_determinism_t1_9() -> None:
    """AC-16, AC-21, FR-15: Identical (seed, config) yields identical fingerprint & results."""
    cfg1 = RunConfig(seed=42, profile_id="synthetic_default", sizes=(100, 500), book_depth=10)
    cfg2 = RunConfig(seed=42, profile_id="synthetic_default", sizes=(100, 500), book_depth=10)

    r1 = run_simulation(
        seed=cfg1.seed,
        profile_id=cfg1.profile_id,
        sizes=cfg1.sizes,
        book_depth=cfg1.book_depth,
    )
    r2 = run_simulation(
        seed=cfg2.seed,
        profile_id=cfg2.profile_id,
        sizes=cfg2.sizes,
        book_depth=cfg2.book_depth,
    )

    assert compute_fingerprint(cfg1) == compute_fingerprint(cfg2)
    assert r1 == r2
    assert r1.event_log_sha256 == r2.event_log_sha256
    assert json.dumps(r1.to_dict(), sort_keys=True) == json.dumps(r2.to_dict(), sort_keys=True)

    # Different seed produces distinct output
    r3 = run_simulation(
        seed=43,
        profile_id=cfg1.profile_id,
        sizes=cfg1.sizes,
        book_depth=cfg1.book_depth,
    )
    assert r3.event_log_sha256 != r1.event_log_sha256
