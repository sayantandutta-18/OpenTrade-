"""AI Analyst service with 4 fixed prompts, demo answers, and 24h live cache (T16.1)."""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from opentrade.llm.guardrails import verify_numbers_grounded
from opentrade.services.errors import ValidationError

DEMO_ANALYST_PATH = Path("data/demo/analyst_answers.json")
ANALYST_CACHE_TTL_SECONDS = 86_400.0  # 24 hours per docs/TRD.md §5

ANALYST_PROMPTS: dict[str, str] = {
    "Correlation": (
        "Explain portfolio correlation, diversification verdict, and effective holdings."
    ),
    "Geography": "Explain geographic and sector spread across the selected companies.",
    "Radar": "Compare factor radar strengths and note any missing traits.",
    "Risk": "Summarize market impact exponent, temporary/permanent slippage, and shock risk.",
}

_ANALYST_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


class LlmClient(Protocol):
    """Protocol for LLM completion providers."""

    def complete(self, system_prompt: str, data_json: str, user_prompt: str) -> str: ...


def run_analyst_prompt(
    prompt_id: str,
    mode: str = "demo",
    context_data: dict[str, Any] | None = None,
    adapter: LlmClient | None = None,
    demo_path: Path = DEMO_ANALYST_PATH,
) -> dict[str, Any]:
    """Run one of the 4 fixed analyst prompts in DEMO or LIVE mode (AC-34 to AC-36)."""
    if prompt_id not in ANALYST_PROMPTS:
        raise ValidationError(f"Unknown analyst prompt: {prompt_id!r}")

    clean_mode = mode.strip().lower()
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = context_data or {}

    if clean_mode != "live" or adapter is None:
        answers = json.loads(demo_path.read_text(encoding="utf-8"))
        return {
            "prompt_id": prompt_id,
            "mode": "DEMO",
            "generated_at": now_str,
            "answer": str(answers.get(prompt_id, "")),
            "provenance": "SYNTHETIC",
            "cached": False,
        }

    data_json = json.dumps(data, sort_keys=True)
    input_hash = hashlib.sha256(data_json.encode("utf-8")).hexdigest()[:16]
    cache_key = (prompt_id, f"{input_hash}:{type(adapter).__name__}")
    now_mono = time.monotonic()
    cached = _ANALYST_CACHE.get(cache_key)
    if cached is not None and (now_mono - cached[0]) < ANALYST_CACHE_TTL_SECONDS:
        return {**cached[1], "cached": True}

    system_prompt = (
        "You are OpenTrade's read-only simulation analyst. Use ONLY numbers present in DATA_JSON. "
        "Do not invent or extrapolate any new numbers. Never give investment advice."
    )
    reply = adapter.complete(system_prompt, data_json, ANALYST_PROMPTS[prompt_id])
    ungrounded = verify_numbers_grounded(reply, data)
    if ungrounded:
        raise ValidationError(f"Live analyst response contained ungrounded numbers: {ungrounded}")

    result = {
        "prompt_id": prompt_id,
        "mode": "LIVE",
        "generated_at": now_str,
        "answer": reply,
        "provenance": str(data.get("provenance", "SYNTHETIC")),
        "cached": False,
    }
    _ANALYST_CACHE[cache_key] = (now_mono, result)
    return result
