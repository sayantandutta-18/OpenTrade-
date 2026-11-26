"""Guardrails for advice detection and numeric grounding (AC-36, AC-38, SECURITY T-8)."""

import re
from typing import Any

ADVICE_REFUSAL_TEXT = (
    "I cannot recommend what to buy or sell or give investment advice. "
    "I can explain the simulation metrics or correlation numbers instead."
)

_ADVICE_PATTERNS = (
    r"\bwhat\s+should\s+i\s+(buy|sell|invest|trade|purchase)\b",
    r"\bwhich\s+(stock|ticker|company|stocks)\b.*\b(should\s+i|will\s+go\s+up|best|purchase|buy|sell)\b",
    r"\bshould\s+i\s+(buy|sell|go\s+long|go\s+short|invest)\b",
    r"\b(recommend|advise|suggest)\b.*\b(stock|trade|buy|sell|portfolio|buying|selling)\b",
    r"\b(tell\s+me\s+what\s+to\s+sell|what\s+trade\s+should\s+i\s+place|stocks\s+to\s+purchase)\b",
    r"\b(investment\s+advice|hot\s+stock\s+tip|winning\s+stock|guaranteed\s+to\s+profit|best\s+stock)\b",
    r"\bhow\s+should\s+i\s+allocate\b",
    r"\bwill\s+rise\b",
    r"\bis\s+\w+\s+a\s+buy\s+or\s+a\s+sell\b",
    r"\badvise\s+me\b",
)

_COMPILED_ADVICE = [re.compile(pat, re.IGNORECASE) for pat in _ADVICE_PATTERNS]
_NUM_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?")


def is_advice_request(text: str) -> bool:
    """Return True if text asks for personalized investment advice or trade picks (AC-38)."""
    clean = " ".join((text or "").strip().split())
    return any(pattern.search(clean) for pattern in _COMPILED_ADVICE)


def _collect_numbers(obj: Any, out: set[float]) -> None:
    """Recursively collect all numeric values from nested dicts/lists."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
        return
    if isinstance(obj, str):
        for match in _NUM_RE.findall(obj):
            try:
                out.add(float(match))
            except ValueError:
                continue
        return
    if isinstance(obj, dict):
        for val in obj.values():
            _collect_numbers(val, out)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            _collect_numbers(item, out)


def verify_numbers_grounded(reply_text: str, source_data: Any) -> list[str]:
    """Return any numbers in reply_text that do not match numbers in source_data (AC-36)."""
    allowed: set[float] = set()
    _collect_numbers(source_data, allowed)

    ungrounded: list[str] = []
    for raw in _NUM_RE.findall(reply_text):
        val = float(raw)
        if not any(abs(val - ref) <= 1e-6 for ref in allowed):
            ungrounded.append(raw)
    return ungrounded
