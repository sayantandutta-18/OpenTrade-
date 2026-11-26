"""Verified narrative summary generator cross-checked against saved results (T21.1)."""

from typing import Any

from opentrade.llm.guardrails import verify_numbers_grounded


def generate_verified_summary(run_payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a plain-language run summary and verify every number against run_payload."""
    fp = str(run_payload.get("fingerprint", "unknown"))
    seed = int(run_payload.get("seed", 42))
    prov = str(run_payload.get("provenance", "SYNTHETIC"))
    results = run_payload.get("results", {})
    fit = results.get("fit", {})
    decay = results.get("decay", {})

    beta = float(fit.get("beta", 0.0))
    ci95 = fit.get("ci95", [beta, beta])
    temp_bps = float(decay.get("temporary_impact_bps", 0.0))
    perm_bps = float(decay.get("permanent_impact_bps", 0.0))

    text = (
        f"In this simulation (run {fp}, seed {seed}, {prov}), the fitted market impact "
        f"exponent is {beta} with confidence interval [{ci95[0]}, {ci95[1]}]. "
        f"Temporary impact was {temp_bps} bps and permanent impact was {perm_bps} bps."
    )
    ungrounded = verify_numbers_grounded(text, run_payload)
    return {
        "fingerprint": fp,
        "provenance": prov,
        "text": text,
        "verified": len(ungrounded) == 0,
        "ungrounded_numbers": ungrounded,
    }
