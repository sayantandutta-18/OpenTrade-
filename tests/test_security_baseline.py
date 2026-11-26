"""Release verification T-X.3: Security baseline checks (SECURITY.md section 10)."""

import re
from pathlib import Path

import pytest

from opentrade.adapters.news_rss import RssAdapterError, parse_rss_xml
from opentrade.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = REPO_ROOT / "opentrade"


def test_no_hardcoded_secrets_in_package_tx3() -> None:
    """T-X.3: No hardcoded API keys or private keys in opentrade/."""
    secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    ]
    for py_file in PKG_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for pat in secret_patterns:
            assert not pat.search(text), f"Potential hardcoded secret in {py_file}"


def test_settings_repr_redacts_secrets_tx3() -> None:
    """T-X.3 / SECURITY T-10: Settings.__repr__ redacts secret_key, smtp_password, and api keys."""
    s = Settings(
        environment="development",
        secret_key="super-secret-value-xyz",
        base_url="http://localhost:8501",
        smtp_password="smtp-secret-password",
        twelve_data_api_key="td-secret-key",
        llm_api_key="llm-secret-key",
    )
    rendered = repr(s)
    assert "super-secret-value-xyz" not in rendered
    assert "smtp-secret-password" not in rendered
    assert "td-secret-key" not in rendered
    assert "llm-secret-key" not in rendered
    assert "[REDACTED]" in rendered


def test_rss_adapter_rejects_xxe_payload_tx3() -> None:
    """T-X.3: RSS XML parser rejects DOCTYPE/ENTITY declarations (XXE protection)."""
    xxe_xml = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<rss><channel><item><title>&xxe;</title></item></channel></rss>"
    )
    with pytest.raises(RssAdapterError):
        parse_rss_xml(xxe_xml, default_source="Test")


def test_phase16_to_22_python_files_under_400_lines_tx3() -> None:
    """CODING_STANDARDS.md: Every Phase 16-22 Python file is strictly under 400 lines."""
    phase16_22_files = [
        PKG_ROOT / "engine" / "validation.py",
        PKG_ROOT / "engine" / "numba_kernels.py",
        PKG_ROOT / "storage" / "chat_repo.py",
        PKG_ROOT / "adapters" / "llm.py",
        PKG_ROOT / "llm" / "guardrails.py",
        PKG_ROOT / "services" / "analyst.py",
        PKG_ROOT / "services" / "narrative.py",
        PKG_ROOT / "services" / "assistant.py",
        PKG_ROOT / "services" / "chat.py",
        PKG_ROOT / "services" / "replay.py",
        PKG_ROOT / "services" / "simulator.py",
        PKG_ROOT / "services" / "runs.py",
        PKG_ROOT / "ui" / "components" / "chat_panel.py",
        PKG_ROOT / "ui" / "pages" / "analyst.py",
        PKG_ROOT / "ui" / "pages" / "run_history.py",
        PKG_ROOT / "ui" / "pages" / "tour.py",
        PKG_ROOT / "ui" / "pages" / "summary.py",
        PKG_ROOT / "ui" / "pages" / "validation.py",
    ]
    for py_file in phase16_22_files:
        line_count = len(py_file.read_text(encoding="utf-8").splitlines())
        assert line_count < 400, f"{py_file} has {line_count} lines (must be < 400)"
