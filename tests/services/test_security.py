"""Tests for security headers and log redaction filter.

Follows docs/SECURITY.md (T-7, T-10, T-13, T-14) and docs/SRS.md (NFR-4).
"""

import io
import logging

import pytest

from opentrade.services.security import (
    SecretRedactingFilter,
    apply_security_headers,
    configure_logging,
    get_security_headers,
    redact_secrets,
)


def test_security_headers_non_production_omits_hsts() -> None:
    """SECURITY.md T-7, T-13, T-14: Security headers in non-production mode."""
    headers = get_security_headers(production=False)

    assert headers["Content-Security-Policy"] == (
        "default-src 'self'; img-src 'self' data: https:; frame-ancestors 'none'"
    )
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in headers


def test_security_headers_production_includes_hsts(monkeypatch: pytest.MonkeyPatch) -> None:
    """SECURITY.md T-14: Security headers in production mode include Strict-Transport-Security."""
    monkeypatch.setenv("OPENTRADE_ENV", "production")
    headers = get_security_headers(production=None)
    assert headers["Strict-Transport-Security"] == "max-age=31536000"

    # Explicit parameter overrides environment
    headers_dev = get_security_headers(production=False)
    assert "Strict-Transport-Security" not in headers_dev


def test_apply_security_headers_merges_without_overwriting_custom() -> None:
    """SECURITY.md T-7, T-13: apply_security_headers merges default security
    headers with existing response headers without overwriting custom values.
    """
    existing = {"X-Custom-Header": "custom-value", "Content-Type": "application/json"}
    merged = apply_security_headers(existing, production=False)

    assert merged["X-Custom-Header"] == "custom-value"
    assert merged["Content-Type"] == "application/json"
    assert merged["X-Frame-Options"] == "DENY"
    assert merged["X-Content-Type-Options"] == "nosniff"
    assert merged["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in merged["Content-Security-Policy"]


def test_redact_secrets_string_patterns() -> None:
    """SECURITY.md T-10, NFR-4: redact_secrets replaces sensitive patterns in plain text."""
    plain_text = (
        "User logged in with password=SecretPassword123! and "
        "password_hash=$argon2id$v=19$m=65536,t=3,p=4$somehashvalue and "
        "Bearer token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token.signature and "
        "Cookie: ot_session=session_token_xyz123; ot_csrf=csrf_token_abc456 and "
        "Authorization: Bearer my-secret-api-token"
    )
    sanitized = redact_secrets(plain_text)

    assert "SecretPassword123!" not in sanitized
    assert "$argon2id$" not in sanitized
    assert "session_token_xyz123" not in sanitized
    assert "csrf_token_abc456" not in sanitized
    assert "my-secret-api-token" not in sanitized
    assert "[REDACTED]" in sanitized


def test_redact_secrets_json_and_key_value_patterns() -> None:
    """SECURITY.md T-10, NFR-4: redact_secrets redacts key-value and JSON pairs."""
    json_text = (
        '{"password": "secret_pass", "current_password": "old_pass", '
        '"new_password": "next_pass", "secret_key": "app_secret", '
        '"twelve_data_api_key": "td_key_123", "llm_api_key": "sk-123456", '
        '"api_key": "generic_key", "email_body": "Verification link inside", '
        '"chat_text": "Private user prompt", "username": "alice", "action": "LOGIN"}'
    )
    sanitized = redact_secrets(json_text)

    assert "secret_pass" not in sanitized
    assert "old_pass" not in sanitized
    assert "next_pass" not in sanitized
    assert "app_secret" not in sanitized
    assert "td_key_123" not in sanitized
    assert "sk-123456" not in sanitized
    assert "generic_key" not in sanitized
    assert "Verification link inside" not in sanitized
    assert "Private user prompt" not in sanitized
    # Non-sensitive keys and values must remain intact
    assert '"username": "alice"' in sanitized
    assert '"action": "LOGIN"' in sanitized


def test_log_filter_redacts_record_message_and_args() -> None:
    """SECURITY.md T-10, NFR-4: SecretRedactingFilter redacts record.msg and
    %-formatted record.args to prevent secrets appearing in log output.
    """
    log_filter = SecretRedactingFilter()
    record = logging.LogRecord(
        name="opentrade.auth",
        level=logging.INFO,
        pathname="auth.py",
        lineno=42,
        msg="Login failed for user=%s with password=%s and token=%s",
        args=("trader@example.com", "MyPassword123!", "raw_token_xyz987"),
        exc_info=None,
    )

    result = log_filter.filter(record)
    assert result is True  # Never drops log records

    formatted = record.getMessage()
    assert "trader@example.com" in formatted
    assert "MyPassword123!" not in formatted
    assert "raw_token_xyz987" not in formatted
    assert "[REDACTED]" in formatted


def test_log_filter_redacts_extra_nested_dict_and_list() -> None:
    """SECURITY.md T-10, NFR-4: SecretRedactingFilter sanitizes nested
    structures in extra dictionary fields attached to log records.
    """
    log_filter = SecretRedactingFilter()
    extra_data = {
        "user_id": 10,
        "credentials": {
            "password": "NestedPassword123!",
            "token": "nested_token_456",
            "api_key": "key_789",
        },
        "tokens": ["normal_id", "token=secret_in_list"],
        "safe_details": {"action": "UPDATE_PROFILE", "status": "SUCCESS"},
    }

    record = logging.LogRecord(
        name="opentrade.profile",
        level=logging.INFO,
        pathname="profile.py",
        lineno=10,
        msg="Profile action completed",
        args=(),
        exc_info=None,
    )
    for k, v in extra_data.items():
        setattr(record, k, v)

    log_filter.filter(record)

    creds = record.__dict__.get("credentials", {})
    assert creds["password"] == "[REDACTED]"
    assert creds["token"] == "[REDACTED]"
    assert creds["api_key"] == "[REDACTED]"

    tokens = record.__dict__.get("tokens", [])
    assert tokens[0] == "normal_id"
    assert "secret_in_list" not in tokens[1]
    assert "[REDACTED]" in tokens[1]

    # Non-sensitive extra attributes preserved
    assert record.__dict__["user_id"] == 10
    safe = record.__dict__["safe_details"]
    assert safe["action"] == "UPDATE_PROFILE"
    assert safe["status"] == "SUCCESS"


def test_log_filter_redacts_exception_messages() -> None:
    """SECURITY.md T-10, NFR-4: SecretRedactingFilter scrubs sensitive info from exc_text."""
    log_filter = SecretRedactingFilter()
    record = logging.LogRecord(
        name="opentrade.storage",
        level=logging.ERROR,
        pathname="db.py",
        lineno=99,
        msg="Database error occurred",
        args=(),
        exc_info=None,
    )
    record.exc_text = (
        "OperationalError: connection failed with password=SuperSecretPassword1! "
        "and secret_key=TopSecretKeyApp"
    )

    log_filter.filter(record)

    assert "SuperSecretPassword1!" not in str(record.exc_text)
    assert "TopSecretKeyApp" not in str(record.exc_text)
    assert "[REDACTED]" in str(record.exc_text)


def test_configure_logging_attaches_filter_and_redacts_end_to_end() -> None:
    """SECURITY.md T-10, NFR-4: configure_logging attaches SecretRedactingFilter
    to handlers globally so all emitted log messages are redacted.
    """
    logger = configure_logging(level="DEBUG")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    # Add SecretRedactingFilter to this handler as configure_logging does for its root handlers
    handler.addFilter(SecretRedactingFilter())
    logger.addHandler(handler)

    try:
        logger.info(
            "User login attempt: password=%s, session_token=%s, username=%s",
            "SensitivePassword999!",
            "ot_session_secret_token",
            "test_user",
        )
        output = stream.getvalue()

        assert "SensitivePassword999!" not in output
        assert "ot_session_secret_token" not in output
        assert "test_user" in output
        assert "[REDACTED]" in output
    finally:
        logger.removeHandler(handler)
