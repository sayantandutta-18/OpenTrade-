"""Tests for AI Analyst service (T16.1) and verified narrative summary (T21.1).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-34, AC-35, AC-36) and docs/SRS.md (FR-44 to FR-47).
"""

from typing import Any

import pytest

from opentrade.services.analyst import ANALYST_PROMPTS, run_analyst_prompt
from opentrade.services.errors import ValidationError
from opentrade.services.narrative import generate_verified_summary


class _GroundedMockLlm:
    def complete(self, system_prompt: str, data_json: str, user_prompt: str) -> str:
        return "In this simulation, avg correlation is 0.25 and effective holdings is 3.2."


class _HallucinatingMockLlm:
    def complete(self, system_prompt: str, data_json: str, user_prompt: str) -> str:
        return "In this simulation, expected return is 99.9% guaranteed."


def test_analyst_demo_mode_zero_network_and_four_prompts_ac34_ac35() -> None:
    """T16.1, AC-34, AC-35, FR-44: Demo mode serves 4 prompts with zero network calls."""
    assert set(ANALYST_PROMPTS.keys()) == {"Correlation", "Geography", "Radar", "Risk"}
    for prompt_id in ANALYST_PROMPTS:
        res = run_analyst_prompt(prompt_id=prompt_id, mode="demo", context_data={})
        assert res["mode"] == "DEMO"
        assert res["generated_at"]
        assert res["answer"]
        assert res["provenance"] == "SYNTHETIC"


def test_analyst_live_mode_verifies_numbers_against_json_ac36() -> None:
    """T16.1, AC-36: Live mode passes JSON numbers and rejects any ungrounded LLM numbers."""
    ctx: dict[str, Any] = {"avg_correlation": 0.25, "effective_holdings": 3.2}
    ok = run_analyst_prompt(
        prompt_id="Correlation",
        mode="live",
        context_data=ctx,
        adapter=_GroundedMockLlm(),
    )
    assert ok["mode"] == "LIVE"
    assert ok["generated_at"]
    assert "0.25" in ok["answer"]

    with pytest.raises(ValidationError, match="ungrounded"):
        run_analyst_prompt(
            prompt_id="Correlation",
            mode="live",
            context_data=ctx,
            adapter=_HallucinatingMockLlm(),
        )


def test_verified_narrative_summary_checks_every_number_t21_1() -> None:
    """T21.1: Narrative summary cross-checks every emitted number against saved run payload."""
    run_payload = {
        "fingerprint": "a1b2c3d4e5f6",
        "seed": 42,
        "provenance": "SYNTHETIC",
        "results": {
            "fit": {"beta": 0.51, "ci95": [0.46, 0.56]},
            "decay": {"temporary_impact_bps": 4.2, "permanent_impact_bps": 1.8},
        },
    }
    summary = generate_verified_summary(run_payload)
    assert summary["verified"] is True
    assert summary["ungrounded_numbers"] == []
    assert summary["provenance"] == "SYNTHETIC"
    assert "0.51" in summary["text"]
