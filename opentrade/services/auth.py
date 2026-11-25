"""Authentication service and endpoints per docs/API_SPEC.md and docs/SECURITY.md."""

import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, overload

from opentrade.adapters.email_smtp import send_email
from opentrade.services.clock import (
    add_days_from_iso,
    add_days_iso,
    add_hours_iso,
    add_minutes_iso,
    hours_ago_iso,
    is_expired,
    is_within_minutes,
    now_iso,
)
from opentrade.services.errors import (
    AccountLockedError,
    AppError,
    RateLimitedError,
    TokenInvalidError,
    UnauthenticatedError,
    ValidationError,
)
from opentrade.services.security import (
    generate_token,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)
from opentrade.storage.db import get_connection
from opentrade.storage.repositories import (
    SessionRepository,
    TokenRepository,
    UserRepository,
    UserRow,
)

# RFC 5322 compatible simplified email pattern
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$")

# Precomputed Argon2id hash for constant-latency verification against non-existent accounts
_DUMMY_ARGON2_HASH = hash_password("dummy-password-for-anti-enumeration")

# In-memory IP rate limiter for login attempts: client_ip -> list of monotonic timestamps
_LOGIN_IP_ATTEMPTS: dict[str, list[float]] = {}


def clear_login_ip_rate_limits() -> None:
    """Clear in-memory IP rate limiter records (used for testing)."""
    _LOGIN_IP_ATTEMPTS.clear()


def _check_ip_rate_limit(
    client_ip: str,
    limit: int = 10,
    window_seconds: float = 60.0,
) -> None:
    """Enforce in-memory IP rate limit for login attempts."""
    now = time.monotonic()
    attempts = _LOGIN_IP_ATTEMPTS.get(client_ip, [])
    cutoff = now - window_seconds
    attempts = [t for t in attempts if t > cutoff]
    if len(attempts) >= limit:
        _LOGIN_IP_ATTEMPTS[client_ip] = attempts
        raise RateLimitedError("Too many login attempts from this IP. Please try again later.")
    attempts.append(now)
    _LOGIN_IP_ATTEMPTS[client_ip] = attempts


@dataclass(frozen=True)
class UserView:
    """Safe, public representation of a user at registration."""

    name: str
    email: str
    verified: bool


class EndpointResult(tuple[int, dict[str, Any]]):
    """A tuple of (status, body) that also carries response headers."""

    _headers: dict[str, str]

    def __new__(
        cls,
        status: int,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> "EndpointResult":
        obj = super().__new__(cls, (status, body))
        obj._headers = headers or {}
        return obj

    @property
    def status_code(self) -> int:
        """HTTP status code."""
        return self[0]

    @property
    def body(self) -> dict[str, Any]:
        """Response body payload."""
        return self[1]

    @property
    def headers(self) -> dict[str, str]:
        """Response headers dictionary."""
        return self._headers


def is_production() -> bool:
    """Check whether the application is running in production mode."""
    return os.environ.get("OPENTRADE_ENV") == "production"


def make_session_cookie(
    token: str,
    max_age: int = 1209600,
    secure: bool = False,
) -> str:
    """Format Set-Cookie header for ot_session cookie."""
    parts = [
        f"ot_session={token}",
        "Path=/",
        f"Max-Age={max_age}",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def make_clear_session_cookie(secure: bool = False) -> str:
    """Format Set-Cookie header to clear ot_session cookie on logout."""
    parts = [
        "ot_session=",
        "Path=/",
        "Max-Age=0",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def extract_session_token(cookies: dict[str, str] | str | None) -> str | None:
    """Extract ot_session raw token from dict or Cookie header string."""
    if not cookies:
        return None
    if isinstance(cookies, dict):
        return cookies.get("ot_session")
    for part in cookies.split(";"):
        item = part.strip()
        if item.startswith("ot_session="):
            return item[len("ot_session=") :].strip()
    return None


def validate_email(email: str | None) -> str:
    """Validate email address format and length.

    Args:
        email: Raw email string.

    Returns:
        str: Cleaned, lowercased email address.

    Raises:
        ValidationError: If the email is missing, too long, or malformed.
    """
    if not email or not isinstance(email, str):
        raise ValidationError("Email is required")

    trimmed = email.strip()
    if len(trimmed) > 254:
        raise ValidationError("Email must be at most 254 characters")

    if not _EMAIL_REGEX.match(trimmed):
        raise ValidationError("Invalid email address format")

    return trimmed.lower()


def validate_name(name: str | None) -> str:
    """Validate user name format and length.

    Args:
        name: Raw user name.

    Returns:
        str: Cleaned name string.

    Raises:
        ValidationError: If the name is missing, empty, or exceeds 80 characters.
    """
    if not name or not isinstance(name, str):
        raise ValidationError("Name is required")

    trimmed = name.strip()
    if len(trimmed) < 1 or len(trimmed) > 80:
        raise ValidationError("Name must be between 1 and 80 characters")

    return trimmed


def register_user(
    conn: sqlite3.Connection,
    name: str | None,
    email: str | None,
    password: str | None,
) -> UserView:
    """Register a new user account with validated input and Argon2id hashed password.

    Args:
        conn: Active database connection.
        name: User's full name.
        email: User's email address.
        password: Plain text password to validate and hash.

    Returns:
        UserView: Newly registered user data with verified=False.

    Raises:
        ValidationError: If name or email fails validation.
        WeakPasswordError: If the password violates security rules.
        EmailTakenError: If the email already exists in the database.
    """
    clean_name = validate_name(name)
    clean_email = validate_email(email)

    if not password or not isinstance(password, str):
        raise ValidationError("Password is required")

    # Validate password rules (length, common passwords, name/email equality)
    validate_password(password, name=clean_name, email=clean_email)

    # Hash password with Argon2id; executed unconditionally for similar response timing,
    # not verified by a timing test
    password_hash = hash_password(password)

    repo = UserRepository(conn)

    # Check for existing email (case-insensitive) per ADR-014 and SECURITY.md T-5
    existing = repo.get_by_email(clean_email)
    if existing is not None:
        # ADR-014: Duplicate registration does not reveal email existence.
        # Do not create a row; return standard user representation without id.
        return UserView(
            name=clean_name,
            email=clean_email,
            verified=False,
        )

    now = now_iso()
    user_row = repo.create(
        name=clean_name,
        email=clean_email,
        password_hash=password_hash,
        created_at=now,
        updated_at=now,
    )

    return UserView(
        name=user_row.name,
        email=user_row.email,
        verified=False,
    )


def register_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    """Handler for POST /api/v1/auth/register per docs/API_SPEC.md.

    Args:
        body: JSON request body with keys 'name', 'email', 'password'.
        db_path: Optional path to SQLite database.

    Returns:
        tuple[int, dict[str, Any]]: HTTP status code and response payload.
    """
    request_id = str(uuid.uuid4())
    conn = get_connection(db_path)

    try:
        name = body.get("name")
        email = body.get("email")
        password = body.get("password")

        # Explicitly check if email already exists before calling register_user
        # per ADR-014 (register_user returns identical UserView for both cases).
        clean_email = validate_email(email)
        user_repo = UserRepository(conn)
        existing_user = user_repo.get_by_email(clean_email)

        user = register_user(conn, name=name, email=email, password=password)

        if existing_user is not None:
            # Duplicate email: send security notification to real account owner (ADR-014)
            send_email(
                to=clean_email,
                subject="OpenTrade: Registration attempt with your email",
                body=(
                    "Someone attempted to register an account with your email address. "
                    "If this was you, you can log in or reset your password."
                ),
            )
        else:
            # New user: generate verification token and send verification email
            new_user = user_repo.get_by_email(clean_email)
            if new_user is not None:
                token_repo = TokenRepository(conn)
                now = now_iso()
                token_repo.invalidate_unused_verification_tokens(
                    user_id=new_user.id, invalid_at=now
                )
                raw_token = generate_token(32)
                token_hash = hash_token(raw_token)
                token_repo.create(
                    user_id=new_user.id,
                    purpose="verify_email",
                    token_hash=token_hash,
                    expires_at=add_hours_iso(24),
                    created_at=now,
                )
                send_email(
                    to=clean_email,
                    subject="OpenTrade: Verify your email address",
                    body=f"Please verify your email address by visiting: token={raw_token}",
                )

        return 201, {
            "message": "If this email can be registered, a verification link has been sent.",
            "user": {
                "name": user.name,
                "email": user.email,
                "verified": user.verified,
            },
        }
    except AppError as err:
        err.request_id = request_id
        return err.status_code, err.to_dict()
    except Exception:
        return 500, {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
    finally:
        conn.close()


def verify_email_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    """Handler for POST /api/v1/auth/verify per docs/API_SPEC.md.

    Args:
        body: JSON request body with key 'token'.
        db_path: Optional path to SQLite database.

    Returns:
        tuple[int, dict[str, Any]]: HTTP status code and response payload.
    """
    request_id = str(uuid.uuid4())
    conn = get_connection(db_path)

    try:
        raw_token = body.get("token")
        if not raw_token or not isinstance(raw_token, str):
            raise TokenInvalidError("Verification token is required")

        token_hash = hash_token(raw_token.strip())
        token_repo = TokenRepository(conn)
        token_row = token_repo.get_by_hash(token_hash)

        if token_row is None or token_row.purpose not in ("verify_email", "resend_verify_email"):
            raise TokenInvalidError("Invalid verification token")

        if token_row.used_at is not None:
            raise TokenInvalidError("Verification token has already been used")

        if is_expired(token_row.expires_at):
            raise TokenInvalidError("Verification token has expired")

        now = now_iso()
        token_repo.mark_used(token_row.id, used_at=now)

        user_repo = UserRepository(conn)
        user_repo.update_email_verified_at(token_row.user_id, verified_at=now)

        return 200, {"verified": True}
    except AppError as err:
        err.request_id = request_id
        return err.status_code, err.to_dict()
    except Exception:
        return 500, {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
    finally:
        conn.close()


def resend_verification_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    """Handler for POST /api/v1/auth/resend-verification per docs/API_SPEC.md.

    Args:
        body: JSON request body with key 'email'.
        db_path: Optional path to SQLite database.

    Returns:
        tuple[int, dict[str, Any]]: HTTP status code and response payload.
    """
    request_id = str(uuid.uuid4())
    conn = get_connection(db_path)

    try:
        email = body.get("email")
        if not email or not isinstance(email, str):
            raise ValidationError("Email is required")

        clean_email = validate_email(email)
        user_repo = UserRepository(conn)
        user = user_repo.get_by_email(clean_email)

        # Anti-enumeration: if user doesn't exist or already verified, return generic 202
        if user is None or user.email_verified_at is not None:
            return 202, {
                "message": ("If this email can receive verification, a new link has been sent.")
            }

        token_repo = TokenRepository(conn)
        now = now_iso()
        one_hour_ago = hours_ago_iso(1)

        # Rate limit: max 3 requests per hour
        recent_count = token_repo.count_recent_tokens(
            user_id=user.id, purpose="resend_verify_email", since_iso=one_hour_ago
        )
        if recent_count >= 3:
            raise RateLimitedError("Too many verification requests. Please wait an hour.")

        # Invalidate earlier unused verification tokens for this user
        token_repo.invalidate_unused_verification_tokens(user_id=user.id, invalid_at=now)

        raw_token = generate_token(32)
        token_hash = hash_token(raw_token)
        token_repo.create(
            user_id=user.id,
            purpose="resend_verify_email",
            token_hash=token_hash,
            expires_at=add_hours_iso(24),
            created_at=now,
        )

        send_email(
            to=clean_email,
            subject="OpenTrade: Verify your email address",
            body=f"Please verify your email address by visiting: token={raw_token}",
        )

        return 202, {"message": "If this email can receive verification, a new link has been sent."}
    except AppError as err:
        err.request_id = request_id
        return err.status_code, err.to_dict()
    except Exception:
        return 500, {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
    finally:
        conn.close()


def login_user(
    conn: sqlite3.Connection,
    email: str | None,
    password: str | None,
) -> UserRow:
    """Authenticate a user with email and password, enforcing lockout rules.

    Args:
        conn: Active database connection.
        email: Raw email input.
        password: Plain text password input.

    Returns:
        UserRow: Authenticated user database row.

    Raises:
        ValidationError: If email or password is missing or malformed.
        AccountLockedError: If the account is currently locked (HTTP 423).
        UnauthenticatedError: If email not found or password incorrect (HTTP 401).
    """
    clean_email = validate_email(email)

    if not password or not isinstance(password, str):
        raise ValidationError("Password is required")

    repo = UserRepository(conn)
    user = repo.get_by_email(clean_email)

    # Anti-enumeration (SECURITY.md T-5): If user doesn't exist, execute dummy Argon2id
    # verification so that response latency is similar to an existing account.
    if user is None:
        verify_password(password, _DUMMY_ARGON2_HASH)
        raise UnauthenticatedError("Invalid email or password")

    # Check lockout (AC-4 & FR-5): If locked_until is set and has not expired, return 423
    if user.locked_until is not None and not is_expired(user.locked_until):
        raise AccountLockedError()

    # Verify password against stored hash
    is_valid = verify_password(password, user.password_hash)

    now = now_iso()
    if not is_valid:
        # Check 10-minute failure sliding window against updated_at
        new_failed = user.failed_logins + 1 if is_within_minutes(user.updated_at, 10) else 1

        # 5 failures locks the account for 15 minutes
        locked_until = add_minutes_iso(15) if new_failed >= 5 else None

        repo.record_failed_login(
            user_id=user.id,
            failed_logins=new_failed,
            locked_until=locked_until,
            updated_at=now,
        )
        raise UnauthenticatedError("Invalid email or password")

    # Password is valid; reset failed_logins and clear any previous lockout
    repo.reset_failed_logins(user_id=user.id, updated_at=now)
    return user


def authenticate_session(
    conn: sqlite3.Connection,
    raw_token: str | None,
) -> UserRow:
    """Authenticate request via raw session token from ot_session cookie.

    Args:
        conn: Active database connection.
        raw_token: Raw token string from cookie.

    Returns:
        UserRow: Authenticated user database row.

    Raises:
        UnauthenticatedError: If token is missing, invalid, or expired.
    """
    if not raw_token:
        raise UnauthenticatedError("Authentication required")

    token_hash = hash_token(raw_token)
    session_repo = SessionRepository(conn)
    session = session_repo.get_by_hash(token_hash)
    if session is None:
        raise UnauthenticatedError("Authentication required")

    now = now_iso()
    # Check idle expiration (> 14 days) and absolute expiration (> 30 days from creation)
    absolute_expiry = add_days_from_iso(session.created_at, 30)
    is_idle_expired = is_expired(session.expires_at)
    is_absolute_expired = is_expired(absolute_expiry)

    if is_idle_expired or is_absolute_expired:
        # Delete stale expired row per SECURITY.md before raising 401
        session_repo.delete_by_id(session.id)
        raise UnauthenticatedError("Session expired")

    # Slide session window: extend by 14 days, capped at created_at + 30 days
    new_expiry = min(add_days_iso(14), absolute_expiry)
    session_repo.touch(session_id=session.id, last_seen_at=now, expires_at=new_expiry)

    user_repo = UserRepository(conn)
    user = user_repo.get_by_id(session.user_id)
    if user is None:
        raise UnauthenticatedError("Authentication required")

    return user


@overload
def login_endpoint(
    body: dict[str, Any],
    client_ip: str = "127.0.0.1",
    user_agent: str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def login_endpoint(
    body: dict[str, Any],
    client_ip: str = "127.0.0.1",
    user_agent: str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def login_endpoint(
    body: dict[str, Any],
    client_ip: str = "127.0.0.1",
    user_agent: str | None = None,
    db_path: str | Path | None = None,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for POST /api/v1/auth/login per docs/API_SPEC.md.

    Args:
        body: JSON request body with keys 'email' and 'password'.
        client_ip: Remote IP address of client for rate limiting.
        user_agent: Optional User-Agent string from request.
        db_path: Optional path to SQLite database.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())

    try:
        # Rate limit: max 10 requests per minute from the same IP (SECURITY.md T-2)
        _check_ip_rate_limit(client_ip=client_ip, limit=10, window_seconds=60.0)

        if not isinstance(body, dict):
            raise ValidationError("Request body must be a JSON object")

        conn = get_connection(db_path)
        try:
            email = body.get("email")
            password = body.get("password")

            user = login_user(conn, email=email, password=password)

            # Issue session token (SECURITY.md §4: 32 random bytes, base64url encoded)
            raw_token = generate_token(32)
            token_hash = hash_token(raw_token)
            user_agent_hash = hash_token(user_agent) if user_agent else None
            now = now_iso()
            expires_at = add_days_iso(14)

            session_repo = SessionRepository(conn)
            session_repo.create(
                user_id=user.id,
                token_hash=token_hash,
                created_at=now,
                expires_at=expires_at,
                last_seen_at=now,
                user_agent_hash=user_agent_hash,
            )

            secure = is_production()
            cookie_header = make_session_cookie(token=raw_token, max_age=1209600, secure=secure)
            headers = {"Set-Cookie": cookie_header}

            body_dict = {
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "verified": user.email_verified_at is not None,
                }
            }
            if include_headers:
                return 200, body_dict, headers
            return EndpointResult(200, body_dict, headers)
        finally:
            conn.close()
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})


@overload
def me_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def me_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def me_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for GET /api/v1/me per docs/API_SPEC.md.

    Args:
        cookies: Client cookies dict or Cookie header string.
        db_path: Optional path to SQLite database.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    conn = get_connection(db_path)
    try:
        raw_token = extract_session_token(cookies)
        user = authenticate_session(conn, raw_token)

        resp_body = {
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "verified": user.email_verified_at is not None,
            }
        }
        if include_headers:
            return 200, resp_body, {}
        return EndpointResult(200, resp_body, {})
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})
    finally:
        conn.close()


@overload
def logout_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def logout_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def logout_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for POST /api/v1/auth/logout per docs/API_SPEC.md.

    Ends the current session, deletes the session row, and clears cookie.

    Args:
        cookies: Client cookies dict or Cookie header string.
        db_path: Optional path to SQLite database.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    conn = get_connection(db_path)
    try:
        raw_token = extract_session_token(cookies)
        if raw_token:
            token_hash = hash_token(raw_token)
            session_repo = SessionRepository(conn)
            session_repo.delete_by_hash(token_hash)

        secure = is_production()
        headers = {"Set-Cookie": make_clear_session_cookie(secure=secure)}
        body: dict[str, Any] = {}
        if include_headers:
            return 204, body, headers
        return EndpointResult(204, body, headers)
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})
    finally:
        conn.close()


@overload
def logout_all_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def logout_all_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def logout_all_endpoint(
    cookies: dict[str, str] | str | None = None,
    db_path: str | Path | None = None,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for POST /api/v1/auth/logout-all per docs/API_SPEC.md (AC-9, FR-6).

    Ends all sessions for the authenticated user and clears cookie.

    Args:
        cookies: Client cookies dict or Cookie header string.
        db_path: Optional path to SQLite database.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    conn = get_connection(db_path)
    try:
        raw_token = extract_session_token(cookies)
        user = authenticate_session(conn, raw_token)

        session_repo = SessionRepository(conn)
        session_repo.delete_all_for_user(user.id)

        secure = is_production()
        headers = {"Set-Cookie": make_clear_session_cookie(secure=secure)}
        body: dict[str, Any] = {}
        if include_headers:
            return 204, body, headers
        return EndpointResult(204, body, headers)
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})
    finally:
        conn.close()


def forgot_password_user(conn: sqlite3.Connection, email: str | None) -> None:
    """Handle password reset request logic per docs/API_SPEC.md §2 and docs/SECURITY.md §5.

    Args:
        conn: Active database connection.
        email: Email address requesting password reset.

    Raises:
        ValidationError: If email is missing, malformed, or invalid.
    """
    if not email or not isinstance(email, str):
        raise ValidationError("Email is required")

    clean_email = validate_email(email)
    user_repo = UserRepository(conn)
    user = user_repo.get_by_email(clean_email)

    if user is None:
        # Match cryptographic and timing characteristics without revealing account existence
        _dummy_tok = generate_token(32)
        _dummy_hash = hash_token(_dummy_tok)
        return

    token_repo = TokenRepository(conn)
    now = now_iso()
    one_hour_ago = hours_ago_iso(1)

    # Rate limit: max 3 requests per hour per email (docs/API_SPEC.md §9)
    recent_count = token_repo.count_recent_tokens(
        user_id=user.id, purpose="reset_password", since_iso=one_hour_ago
    )
    if recent_count >= 3:
        # Return 202 without revealing rate limit or sending email
        return

    # Invalidate earlier unused reset tokens for this user
    token_repo.invalidate_unused_tokens(user_id=user.id, purpose="reset_password", invalid_at=now)

    raw_token = generate_token(32)
    token_hash = hash_token(raw_token)
    token_repo.create(
        user_id=user.id,
        purpose="reset_password",
        token_hash=token_hash,
        expires_at=add_minutes_iso(30),
        created_at=now,
    )

    send_email(
        to=clean_email,
        subject="OpenTrade: Password reset",
        body=f"Reset your password by visiting: token={raw_token}",
    )


@overload
def forgot_password_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def forgot_password_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def forgot_password_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for POST /api/v1/auth/password/forgot per docs/API_SPEC.md §2.

    Args:
        body: JSON request body with 'email'.
        db_path: Optional path to SQLite database.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    if not isinstance(body, dict):
        err = ValidationError("Request body must be a JSON object")
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})

    conn = get_connection(db_path)
    try:
        email = body.get("email")
        forgot_password_user(conn, email=email)

        body_dict = {"message": "If this email is registered, a password reset link has been sent."}
        if include_headers:
            return 202, body_dict, {}
        return EndpointResult(202, body_dict, {})
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})
    finally:
        conn.close()


def reset_password_user(
    conn: sqlite3.Connection,
    raw_token: str | None,
    new_password: str | None,
) -> None:
    """Reset user password using valid reset token per docs/API_SPEC.md §2 and AC-5.

    Args:
        conn: Active database connection.
        raw_token: 32-byte raw token from email.
        new_password: Plain text new password.

    Raises:
        ValidationError: If token or password is missing.
        TokenInvalidError: If token is invalid, wrong purpose, used, or expired.
        WeakPasswordError: If password violates security rules.
    """
    if not raw_token or not isinstance(raw_token, str) or not raw_token.strip():
        raise ValidationError("Token is required")

    if not new_password or not isinstance(new_password, str) or not new_password.strip():
        raise ValidationError("Password is required")

    token_hash = hash_token(raw_token)
    token_repo = TokenRepository(conn)
    token_row = token_repo.get_by_hash(token_hash)

    if (
        token_row is None
        or token_row.purpose != "reset_password"
        or token_row.used_at is not None
        or is_expired(token_row.expires_at)
    ):
        raise TokenInvalidError("Invalid or expired token")

    user_repo = UserRepository(conn)
    user = user_repo.get_by_id(token_row.user_id)
    if user is None:
        raise TokenInvalidError("Invalid or expired token")

    # Validate new password rules before marking token or altering DB
    validate_password(new_password, name=user.name, email=user.email)

    now = now_iso()
    new_hash = hash_password(new_password)
    user_repo.update_password_hash(user_id=user.id, password_hash=new_hash, updated_at=now)
    token_repo.mark_used(token_id=token_row.id, used_at=now)

    # Terminate all active sessions for the user (SECURITY.md §4, API_SPEC.md §2)
    session_repo = SessionRepository(conn)
    session_repo.delete_all_for_user(user.id)


@overload
def reset_password_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def reset_password_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def reset_password_endpoint(
    body: dict[str, Any],
    db_path: str | Path | None = None,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for POST /api/v1/auth/password/reset per docs/API_SPEC.md §2.

    Args:
        body: JSON request body with 'token' and 'new_password'.
        db_path: Optional path to SQLite database.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    if not isinstance(body, dict):
        err = ValidationError("Request body must be a JSON object")
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})

    conn = get_connection(db_path)
    try:
        raw_token = body.get("token")
        new_password = body.get("new_password")

        reset_password_user(conn, raw_token=raw_token, new_password=new_password)

        secure = is_production()
        headers = {"Set-Cookie": make_clear_session_cookie(secure=secure)}
        body_dict: dict[str, Any] = {}
        if include_headers:
            return 204, body_dict, headers
        return EndpointResult(204, body_dict, headers)
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})
    finally:
        conn.close()


def update_profile_user(
    conn: sqlite3.Connection,
    user: UserRow,
    name: str | None,
    email: str | None,
) -> tuple[UserRow, bool]:
    """Update user profile and handle re-verification per docs/API_SPEC.md §2 and FR-8.

    Args:
        conn: Active database connection.
        user: Currently authenticated UserRow.
        name: Optional new user name.
        email: Optional new email address.

    Returns:
        tuple[UserRow, bool]: Updated UserRow and boolean indicating if email changed.

    Raises:
        ValidationError: If neither field provided, invalid format, or email taken.
    """
    if name is None and email is None:
        raise ValidationError("At least one of name or email must be provided")

    new_name = validate_name(name) if name is not None else user.name

    email_changed = False
    new_email = user.email
    if email is not None:
        clean_email = validate_email(email)
        if clean_email != user.email:
            user_repo = UserRepository(conn)
            existing = user_repo.get_by_email(clean_email)
            if existing is not None and existing.id != user.id:
                raise ValidationError("Email is already in use")
            new_email = clean_email
            email_changed = True

    if not email_changed and name is None:
        raise ValidationError("At least one of name or email must be provided")

    now = now_iso()
    new_verified_at = None if email_changed else user.email_verified_at

    user_repo = UserRepository(conn)
    user_repo.update_profile(
        user_id=user.id,
        name=new_name,
        email=new_email,
        email_verified_at=new_verified_at,
        updated_at=now,
    )

    if email_changed:
        token_repo = TokenRepository(conn)
        token_repo.invalidate_unused_verification_tokens(user_id=user.id, invalid_at=now)

        raw_token = generate_token(32)
        token_hash = hash_token(raw_token)
        token_repo.create(
            user_id=user.id,
            purpose="verify_email",
            token_hash=token_hash,
            expires_at=add_hours_iso(24),
            created_at=now,
        )

        send_email(
            to=new_email,
            subject="OpenTrade: Verify your email address",
            body=f"Please verify your email address by visiting: token={raw_token}",
        )

    updated_user = user_repo.get_by_id(user.id)
    if updated_user is None:
        raise RuntimeError("Failed to reload user after profile update")
    return updated_user, email_changed


@overload
def patch_me_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def patch_me_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def patch_me_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for PATCH /api/v1/me per docs/API_SPEC.md §2 and FR-8.

    Args:
        body: JSON request body with optional 'name' and/or 'email'.
        cookies: Client cookies dict or Cookie header string.
        headers: Request headers dictionary.
        db_path: Optional path to SQLite database.
        enforce_csrf: Whether to enforce CSRF checks regardless of cookie presence.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    try:
        if (
            enforce_csrf
            or (isinstance(cookies, dict) and "ot_csrf" in cookies)
            or (isinstance(cookies, str) and "ot_csrf=" in cookies)
        ):
            from opentrade.services.csrf import verify_csrf_token

            verify_csrf_token(method="PATCH", headers=headers, cookies=cookies)

        if not isinstance(body, dict):
            raise ValidationError("Request body must be a JSON object")

        conn = get_connection(db_path)
        try:
            raw_token = extract_session_token(cookies)
            user = authenticate_session(conn, raw_token)

            name = body.get("name")
            email = body.get("email")

            updated_user, _ = update_profile_user(conn, user=user, name=name, email=email)

            body_dict = {
                "user": {
                    "id": updated_user.id,
                    "name": updated_user.name,
                    "email": updated_user.email,
                    "verified": updated_user.email_verified_at is not None,
                }
            }
            if include_headers:
                return 200, body_dict, {}
            return EndpointResult(200, body_dict, {})
        finally:
            conn.close()
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})


def change_password_user(
    conn: sqlite3.Connection,
    user: UserRow,
    current_session_token_hash: str,
    current_password: str | None,
    new_password: str | None,
) -> None:
    """Change user password per docs/API_SPEC.md §2, FR-8, and SECURITY.md §3 & §4.

    Args:
        conn: Active database connection.
        user: Authenticated UserRow.
        current_session_token_hash: SHA-256 hash of active session to preserve.
        current_password: Plain text current password for confirmation.
        new_password: Plain text new password.

    Raises:
        ValidationError: If passwords missing.
        UnauthenticatedError: If current_password does not match user's hash.
        WeakPasswordError: If new_password violates security rules.
    """
    if not current_password or not isinstance(current_password, str):
        raise ValidationError("Current password is required")

    if not new_password or not isinstance(new_password, str):
        raise ValidationError("New password is required")

    if not verify_password(current_password, user.password_hash):
        raise UnauthenticatedError("Invalid current password")

    validate_password(new_password, name=user.name, email=user.email)

    now = now_iso()
    new_hash = hash_password(new_password)
    user_repo = UserRepository(conn)
    user_repo.update_password_hash(user_id=user.id, password_hash=new_hash, updated_at=now)

    # Delete all other sessions for this user, keeping caller's session active (SECURITY.md §4)
    session_repo = SessionRepository(conn)
    session_repo.delete_other_sessions(
        user_id=user.id, current_token_hash=current_session_token_hash
    )


@overload
def change_password_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def change_password_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def change_password_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for POST /api/v1/me/password per docs/API_SPEC.md §2 and FR-8.

    Args:
        body: JSON request body with 'current_password' and 'new_password'.
        cookies: Client cookies dict or Cookie header string.
        headers: Request headers dictionary.
        db_path: Optional path to SQLite database.
        enforce_csrf: Whether to enforce CSRF checks regardless of cookie presence.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    try:
        if (
            enforce_csrf
            or (isinstance(cookies, dict) and "ot_csrf" in cookies)
            or (isinstance(cookies, str) and "ot_csrf=" in cookies)
        ):
            from opentrade.services.csrf import verify_csrf_token

            verify_csrf_token(method="POST", headers=headers, cookies=cookies)

        if not isinstance(body, dict):
            raise ValidationError("Request body must be a JSON object")

        conn = get_connection(db_path)
        try:
            raw_token = extract_session_token(cookies)
            user = authenticate_session(conn, raw_token)
            if not raw_token:
                raise UnauthenticatedError("Authentication required")
            current_session_hash = hash_token(raw_token)

            current_password = body.get("current_password")
            new_password = body.get("new_password")

            change_password_user(
                conn,
                user=user,
                current_session_token_hash=current_session_hash,
                current_password=current_password,
                new_password=new_password,
            )

            body_dict: dict[str, Any] = {}
            if include_headers:
                return 204, body_dict, {}
            return EndpointResult(204, body_dict, {})
        finally:
            conn.close()
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})


def delete_user_account(
    conn: sqlite3.Connection,
    user: UserRow,
    password: str | None,
) -> None:
    """Delete user account after password verification per docs/API_SPEC.md §2 and FR-9.

    Args:
        conn: Active database connection with foreign_keys enabled.
        user: Currently authenticated UserRow.
        password: Plain text password confirmation.

    Raises:
        ValidationError: If password is missing or empty.
        UnauthenticatedError: If password does not match.
    """
    if not password or not isinstance(password, str) or not password.strip():
        raise ValidationError("Password is required")

    if not verify_password(password, user.password_hash):
        raise UnauthenticatedError("Invalid password")

    user_repo = UserRepository(conn)
    user_repo.delete(user.id)


@overload
def delete_me_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: Literal[False] = False,
) -> EndpointResult: ...


@overload
def delete_me_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: Literal[True] = ...,
) -> tuple[int, dict[str, Any], dict[str, str]]: ...


def delete_me_endpoint(
    body: dict[str, Any],
    cookies: dict[str, str] | str | None = None,
    headers: dict[str, str] | None = None,
    db_path: str | Path | None = None,
    enforce_csrf: bool = False,
    include_headers: bool = False,
) -> EndpointResult | tuple[int, dict[str, Any], dict[str, str]]:
    """Handler for DELETE /api/v1/me per docs/API_SPEC.md §2 and FR-9.

    Deletes user and cascades to all child records, clearing session cookie.

    Args:
        body: JSON request body with 'password'.
        cookies: Client cookies dict or Cookie header string.
        headers: Request headers dictionary.
        db_path: Optional path to SQLite database.
        enforce_csrf: Whether to enforce CSRF checks.
        include_headers: Whether to return explicit (status, body, headers) 3-tuple.

    Returns:
        EndpointResult or 3-tuple with status code, response body, and headers.
    """
    request_id = str(uuid.uuid4())
    try:
        if (
            enforce_csrf
            or (isinstance(cookies, dict) and "ot_csrf" in cookies)
            or (isinstance(cookies, str) and "ot_csrf=" in cookies)
        ):
            from opentrade.services.csrf import verify_csrf_token

            verify_csrf_token(method="DELETE", headers=headers, cookies=cookies)

        if not isinstance(body, dict):
            raise ValidationError("Request body must be a JSON object")

        conn = get_connection(db_path)
        try:
            raw_token = extract_session_token(cookies)
            user = authenticate_session(conn, raw_token)

            password = body.get("password")
            delete_user_account(conn, user=user, password=password)

            secure = is_production()
            resp_headers = {"Set-Cookie": make_clear_session_cookie(secure=secure)}
            body_dict: dict[str, Any] = {}
            if include_headers:
                return 204, body_dict, resp_headers
            return EndpointResult(204, body_dict, resp_headers)
        finally:
            conn.close()
    except AppError as err:
        err.request_id = request_id
        if include_headers:
            return err.status_code, err.to_dict(), {}
        return EndpointResult(err.status_code, err.to_dict(), {})
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        if include_headers:
            return 500, err_dict, {}
        return EndpointResult(500, err_dict, {})
