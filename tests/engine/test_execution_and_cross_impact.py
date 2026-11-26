"""Tests for execution strategy ranking (T13.1) and multi-book cross-impact (T15.1).

Follows docs/TASKS.md (T13.1, T15.1) and docs/SRS.md (FR-52).
"""

from opentrade.engine.book import Side
from opentrade.engine.cross_impact import simulate_coupled_books
from opentrade.engine.execution import rank_execution_strategies
from opentrade.engine.profiles import EngineProvenance


def test_execution_strategies_achieve_full_fill_and_rank_by_shortfall_t13_1() -> None:
    """T13.1, FR-52: All execution strategies achieve 100% fill and rank ascending by shortfall."""
    res = rank_execution_strategies(
        profile_id="synthetic_default",
        seed=42,
        total_qty=1200,
        side=Side.BUY,
    )
    assert len(res.rankings) >= 4
    assert all(r.fill_rate == 1.0 for r in res.rankings)
    shortfalls = [r.implementation_shortfall_bps for r in res.rankings]
    assert shortfalls == sorted(shortfalls)
    assert res.provenance is EngineProvenance.SYNTHETIC


def test_coupled_books_generate_emergent_return_correlation_t15_1() -> None:
    """T15.1, FR-52: Cross-impact coupling produces positive emergent correlation between books."""
    coupled = simulate_coupled_books(steps=120, cross_impact_beta=0.8, seed=42)
    uncoupled = simulate_coupled_books(steps=120, cross_impact_beta=0.0, seed=42)

    assert len(coupled.returns_a) == len(coupled.returns_b)
    assert coupled.emergent_correlation > 0.35
    assert coupled.emergent_correlation > uncoupled.emergent_correlation
    assert coupled.provenance is EngineProvenance.SYNTHETIC
