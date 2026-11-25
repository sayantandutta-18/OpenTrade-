"""CSRF token generation, double-submit cookie verification, and middleware.

Follows specifications in docs/SECURITY.md (T-4) and docs/API_SPEC.md (sections 1 and 2).
"""

import functools
import hmac
import secrets
import uuid
from collections.abc import Callable
from typing import Any, Literal, overload

from opentrade.services.auth import EndpointResult, is_production
from opentrade.services.errors import AppError, CsrfFailedError

# Methods that are considered safe/idempotent and bypass CSRF checks per HTTP specs
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def generate_csrf_token() -> str:
    """Generate a cryptographically secure random token using secrets.token_urlsafe(32).

    Returns:
        str: 256-bit URL-safe base64 encoded token.
    """
    return secrets.token_urlsafe(32)


def make_csrf_cookie(token: str, secure: bool = False) -> str:
    """Format Set-Cookie header for ot_csrf cookie per docs/API_SPEC.md.

    Note: Unlike ot_session, ot_csrf does NOT set HttpOnly so that client-side
    scripts can read it to populate X-CSRF-Token on state-changing requests.

    Args:
        token: Raw CSRF token string.
        secure: Whether to include the Secure flag (enabled in production).

    Returns:
        str: Formatted Set-Cookie header value.
    """
    parts = [
        f"ot_csrf={token}",
        "Path=/",
        "SameSite=Lax",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def extract_csrf_token(cookies: dict[str, str] | str | None) -> str | None:
    """Extract ot_csrf token from cookies dictionary or Cookie header string.

    Args:
        cookies: Cookie dictionary or raw Cookie header string.

    Returns:
        str | None: The extracted token if found, or None.
    """
    if not cookies:
        return None
    if isinstance(cookies, dict):
        return cookies.get("ot_csrf")
    for part in cookies.split(";"):
        item = part.strip()
        if item.startswith("ot_csrf="):
            return item[len("ot_csrf=") :].strip()
    return None


def extract_header_token(headers: dict[str, str] | None) -> str | None:
    """Extract X-CSRF-Token from request headers case-insensitively.

    Args:
        headers: Request headers dictionary.

    Returns:
        str | None: Header token value if found, or None.
    """
    if not headers:
        return None
    for key, val in headers.items():
        if key.lower() == "x-csrf-token":
            return val
    return None


def verify_csrf_token(
    method: str,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | str | None = None,
) -> None:
    """Verify double-submit CSRF token on state-changing requests per docs/API_SPEC.md.

    Args:
        method: HTTP method (e.g. 'GET', 'POST', 'PUT', 'PATCH', 'DELETE').
        headers: Request headers dictionary.
        cookies: Request cookies dictionary or Cookie header string.

    Raises:
        CsrfFailedError: If the method is state-changing and the header or cookie is
            missing, empty, or their values do not match (HTTP 403 CSRF_FAILED).
    """
    norm_method = method.strip().upper()
    if norm_method in _SAFE_METHODS:
        return

    header_token = extract_header_token(headers)
    cookie_token = extract_csrf_token(cookies)

    if not header_token or not header_token.strip():
        raise CsrfFailedError("Missing or wrong CSRF token")

    if not cookie_token or not cookie_token.strip():
        raise CsrfFailedError("Missing or wrong CSRF token")

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(header_token.strip(), cookie_token.strip()):
        raise CsrfFailedError("Missing or wrong CSRF token")


@overload
def csrf_token_endpoint(
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def csrf_token_endpoint(
    include_headers: Literal[True],
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def csrf_token_endpoint(
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for GET /api/v1/auth/csrf per docs/API_SPEC.md section 2.

    Generates a new CSRF token, emits the ot_csrf cookie, and returns the token in JSON.

    Args:
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status 200, JSON body, and Set-Cookie header.
    """
    token = generate_csrf_token()
    secure = is_production()
    cookie_header = make_csrf_cookie(token=token, secure=secure)
    headers = {"Set-Cookie": cookie_header}
    body = {"token": token}

    if include_headers:
        return 200, body, headers
    return EndpointResult(200, body, headers)


def csrf_protect(handler: Callable[..., Any]) -> Callable[..., EndpointResult]:
    """Middleware wrapper protecting an endpoint handler with CSRF validation.

    Args:
        handler: Endpoint function to protect.

    Returns:
        Callable: Wrapped endpoint returning EndpointResult.
    """

    @functools.wraps(handler)
    def wrapper(*args: Any, **kwargs: Any) -> EndpointResult:
        method = kwargs.get("method") or (args[0] if args and isinstance(args[0], str) else "POST")
        headers = kwargs.get("headers")
        cookies = kwargs.get("cookies")
        request_id = str(uuid.uuid4())

        try:
            verify_csrf_token(method=str(method), headers=headers, cookies=cookies)
            result = handler(*args, **kwargs)
            if isinstance(result, EndpointResult):
                return result
            if isinstance(result, tuple):
                status_code = result[0]
                resp_body = result[1] if len(result) > 1 else {}
                resp_headers = result[2] if len(result) > 2 else {}
                return EndpointResult(status_code, resp_body, resp_headers)
            return EndpointResult(200, result, {})
        except AppError as err:
            err.request_id = request_id
            return EndpointResult(err.status_code, err.to_dict(), {})
        except Exception:
            err_dict = {
                "error": {
                    "code": "INTERNAL",
                    "message": "An unexpected error occurred",
                    "request_id": request_id,
                }
            }
            return EndpointResult(500, err_dict, {})

    return wrapper
