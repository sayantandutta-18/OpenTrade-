"""Screen-context-aware read-only basic assistant (T17.1)."""

from typing import Any

from opentrade.llm.guardrails import ADVICE_REFUSAL_TEXT, is_advice_request


def answer_screen_question(
    question: str,
    screen_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer a read-only question using screen context, refusing investment advice (AC-38)."""
    if is_advice_request(question):
        return {
            "refused": True,
            "reply": ADVICE_REFUSAL_TEXT,
            "provenance": "SYNTHETIC",
        }

    ctx = screen_context or {}
    run_id = str(ctx.get("run_id") or ctx.get("fingerprint") or "demo-session")
    prov = str(ctx.get("provenance") or "SYNTHETIC")
    screen = str(ctx.get("screen") or "simulator")

    numeric_parts = [
        f"{k}={v}"
        for k, v in ctx.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    metrics_note = ", ".join(numeric_parts) if numeric_parts else "no numeric metrics loaded yet"
    reply = f"On {screen}, the current simulation shows: {metrics_note} " f"(run {run_id}, {prov})."
    return {
        "refused": False,
        "reply": reply,
        "provenance": prov,
    }
