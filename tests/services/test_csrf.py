"""Tests for CSRF token endpoint, validation, and middleware.

Follows docs/SECURITY.md and docs/API_SPEC.md.
"""

from typing import Any

import pytest

from opentrade.services.csrf import (
    csrf_protect,
    csrf_token_endpoint,
    extract_csrf_token,
    generate_csrf_token,
    verify_csrf_token,
)
from opentrade.services.errors import CsrfFailedError


def test_csrf_token_endpoint_returns_token_and_sets_cookie() -> None:
    """API_SPEC.md §1 & §2: GET /auth/csrf returns 200 {"token": ...} and sets ot_csrf cookie."""
    res = csrf_token_endpoint()
    assert res.status_code == 200
    assert "token" in res.body
    token = res.body["token"]
    assert isinstance(token, str)
    assert len(token) >= 32

    assert "Set-Cookie" in res.headers
    cookie_str = res.headers["Set-Cookie"]
    assert f"ot_csrf={token}" in cookie_str
    assert "Path=/" in cookie_str
    assert "SameSite=Lax" in cookie_str
    # ot_csrf must NOT be HttpOnly so JavaScript can read it
    assert "HttpOnly" not in cookie_str
    # In non-production mode, Secure flag is omitted
    assert "Secure" not in cookie_str


def test_csrf_cookie_has_secure_flag_in_production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """SECURITY.md T-4 & T-14: In production mode, ot_csrf cookie includes Secure flag."""
    monkeypatch.setenv("OPENTRADE_ENV", "production")
    res = csrf_token_endpoint()
    assert res.status_code == 200
    assert "Set-Cookie" in res.headers
    cookie_str = res.headers["Set-Cookie"]
    assert "Secure" in cookie_str


def test_safe_methods_bypass_csrf_verification() -> None:
    """API_SPEC.md §1 & SECURITY.md T-4: Safe methods (GET, HEAD, OPTIONS) bypass CSRF checks."""
    for method in ("GET", "HEAD", "OPTIONS", "get", "head", "options"):
        # Even with completely empty headers and cookies, safe methods must not raise
        verify_csrf_token(method=method, headers=None, cookies=None)
        verify_csrf_token(method=method, headers={}, cookies={})


def test_state_changing_methods_succeed_with_matching_header_and_cookie() -> None:
    """API_SPEC.md §1 & SECURITY.md T-4: POST, PUT, PATCH, DELETE succeed when tokens match."""
    token = generate_csrf_token()
    for method in ("POST", "PUT", "PATCH", "DELETE", "post", "put", "patch", "delete"):
        verify_csrf_token(
            method=method,
            headers={"X-CSRF-Token": token},
            cookies={"ot_csrf": token},
        )


def test_case_insensitive_csrf_header_accepted() -> None:
    """API_SPEC.md §1: HTTP header X-CSRF-Token check is case-insensitive."""
    token = generate_csrf_token()
    for header_name in ("X-CSRF-Token", "x-csrf-token", "X-Csrf-Token", "X-CSRF-TOKEN"):
        verify_csrf_token(
            method="POST",
            headers={header_name: token},
            cookies={"ot_csrf": token},
        )


def test_missing_header_rejected_with_403_csrf_failed() -> None:
    """API_SPEC.md §1 & §2: Missing X-CSRF-Token header raises CsrfFailedError (HTTP 403)."""
    token = generate_csrf_token()
    with pytest.raises(CsrfFailedError) as exc_info:
        verify_csrf_token(method="POST", headers={}, cookies={"ot_csrf": token})

    err = exc_info.value
    assert err.status_code == 403
    assert err.code == "CSRF_FAILED"
    data = err.to_dict()
    assert data["error"]["code"] == "CSRF_FAILED"
    assert "request_id" in data["error"]


def test_missing_cookie_rejected_with_403_csrf_failed() -> None:
    """API_SPEC.md §1 & §2: Missing ot_csrf cookie raises CsrfFailedError (HTTP 403)."""
    token = generate_csrf_token()
    with pytest.raises(CsrfFailedError) as exc_info:
        verify_csrf_token(method="POST", headers={"X-CSRF-Token": token}, cookies=None)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "CSRF_FAILED"

    with pytest.raises(CsrfFailedError) as exc_info2:
        verify_csrf_token(method="POST", headers={"X-CSRF-Token": token}, cookies={})

    assert exc_info2.value.status_code == 403
    assert exc_info2.value.code == "CSRF_FAILED"


def test_mismatched_token_rejected_with_403_csrf_failed() -> None:
    """API_SPEC.md §1 & SECURITY.md T-4: Mismatched X-CSRF-Token and ot_csrf raises error."""
    token1 = generate_csrf_token()
    token2 = generate_csrf_token()
    with pytest.raises(CsrfFailedError) as exc_info:
        verify_csrf_token(
            method="POST",
            headers={"X-CSRF-Token": token1},
            cookies={"ot_csrf": token2},
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "CSRF_FAILED"


def test_empty_or_whitespace_tokens_rejected() -> None:
    """API_SPEC.md §1: Empty or whitespace-only CSRF tokens are rejected."""
    with pytest.raises(CsrfFailedError):
        verify_csrf_token(method="POST", headers={"X-CSRF-Token": ""}, cookies={"ot_csrf": ""})

    with pytest.raises(CsrfFailedError):
        verify_csrf_token(
            method="POST",
            headers={"X-CSRF-Token": "   "},
            cookies={"ot_csrf": "   "},
        )


def test_cookie_header_string_parsing() -> None:
    """API_SPEC.md §1: Cookie header string format parsing for ot_csrf."""
    token = generate_csrf_token()
    cookie_str = f"other_cookie=xyz; ot_csrf={token}; session_id=123"

    extracted = extract_csrf_token(cookie_str)
    assert extracted == token

    # Verification passes when cookies are supplied as string
    verify_csrf_token(
        method="POST",
        headers={"X-CSRF-Token": token},
        cookies=cookie_str,
    )


def test_csrf_middleware_protects_handler() -> None:
    """SECURITY.md T-4: Middleware wrapper cleanly protects wrapped endpoint handlers."""

    def mock_endpoint(body: dict[str, Any], **kwargs: Any) -> tuple[int, dict[str, Any]]:
        return 200, {"success": True, "received": body}

    protected = csrf_protect(mock_endpoint)

    token = generate_csrf_token()

    # Safe method GET passes without CSRF headers
    res_get = protected(
        method="GET",
        body={},
        headers={},
        cookies={},
    )
    assert res_get.status_code == 200
    assert res_get.body["success"] is True

    # State-changing method POST without CSRF fails with 403
    res_fail = protected(
        method="POST",
        body={"action": "buy"},
        headers={},
        cookies={"ot_csrf": token},
    )
    assert res_fail.status_code == 403
    assert res_fail.body["error"]["code"] == "CSRF_FAILED"

    # State-changing method POST with valid CSRF succeeds
    res_ok = protected(
        method="POST",
        body={"action": "buy"},
        headers={"X-CSRF-Token": token},
        cookies={"ot_csrf": token},
    )
    assert res_ok.status_code == 200
    assert res_ok.body["success"] is True
    assert res_ok.body["received"] == {"action": "buy"}
