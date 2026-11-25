"""Password rules, token generation, security headers, and log filter per docs/SECURITY.md."""

import hashlib
import logging
import os
import re
import secrets
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any

import argon2
import argon2.exceptions

from opentrade.services.errors import WeakPasswordError

_hasher = argon2.PasswordHasher()
COMMON_PASSWORDS_PATH = Path("data/common_passwords.txt")


@cache
def get_common_passwords(path: Path | None = None) -> frozenset[str]:
    """Load the bundled common passwords list into memory as a case-insensitive set.

    Args:
        path: Optional custom path to common passwords file.

    Returns:
        frozenset[str]: Set of lowercased common passwords.
    """
    target_path = path or COMMON_PASSWORDS_PATH
    if not target_path.is_file():
        return frozenset()

    content = target_path.read_text(encoding="utf-8")
    return frozenset(line.strip().lower() for line in content.splitlines() if line.strip())


def validate_password(
    password: str,
    name: str | None = None,
    email: str | None = None,
    common_passwords_path: Path | None = None,
) -> None:
    """Validate password against security rules in docs/SECURITY.md section 3.

    Rules:
    - Minimum 12 characters, maximum 128 characters.
    - Reject passwords on the bundled 10,001 common passwords list (case-insensitive).
    - Reject passwords equal to the user's name (case-insensitive).
    - Reject passwords equal to the user's email (case-insensitive).

    Args:
        password: Plain text password to validate.
        name: Optional user's name for comparison.
        email: Optional user's email for comparison.
        common_passwords_path: Optional custom path to common passwords file.

    Raises:
        WeakPasswordError: If the password violates any rule, with code WEAK_PASSWORD.
    """
    if not password or len(password) < 12:
        raise WeakPasswordError("Password must be at least 12 characters", code="WEAK_PASSWORD")

    if len(password) > 128:
        raise WeakPasswordError("Password must be at most 128 characters", code="WEAK_PASSWORD")

    normalized_pwd = password.strip().lower()

    if name and normalized_pwd == name.strip().lower():
        raise WeakPasswordError("Password cannot be equal to name", code="WEAK_PASSWORD")

    if email and normalized_pwd == email.strip().lower():
        raise WeakPasswordError("Password cannot be equal to email", code="WEAK_PASSWORD")

    common_passwords = get_common_passwords(common_passwords_path)
    if normalized_pwd in common_passwords:
        raise WeakPasswordError(
            "Password is too common; choose a less predictable password",
            code="WEAK_PASSWORD",
        )


def hash_password(password: str) -> str:
    """Hash password using Argon2id with argon2-cffi library defaults.

    Args:
        password: Plain text password to hash.

    Returns:
        str: Salted Argon2id hash string starting with '$argon2id$'.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain password against an Argon2id hash.

    Args:
        password: Plain text password.
        password_hash: Stored Argon2id hash string.

    Returns:
        bool: True if password matches hash, False otherwise.
    """
    if not password or not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (
        argon2.exceptions.VerificationError,
        argon2.exceptions.InvalidHashError,
    ):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check if the hash was created with parameters different from current library defaults.

    Args:
        password_hash: Stored Argon2id hash string.

    Returns:
        bool: True if the hash needs to be recomputed.
    """
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (
        argon2.exceptions.VerificationError,
        argon2.exceptions.InvalidHashError,
    ):
        return True


def generate_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure random token formatted as base64url.

    Args:
        nbytes: Number of random bytes (default 32 bytes = 256 bits).

    Returns:
        str: URL-safe base64 string without padding.
    """
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Compute the SHA-256 hex digest of a token string.

    Only token hashes are stored in the database per docs/AGENTS.md rule 4.

    Args:
        token: Raw token string.

    Returns:
        str: SHA-256 hex string.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- Security Headers (docs/SECURITY.md §6) ---


def is_production_mode() -> bool:
    """Check whether the application environment is configured as production."""
    env = os.environ.get("OPENTRADE_ENV", "development").strip().lower()
    return env == "production"


def get_security_headers(production: bool | None = None) -> dict[str, str]:
    """Return security headers dictionary per docs/SECURITY.md §6.

    Headers set on every response:
    - Content-Security-Policy: default-src 'self'; img-src 'self' data: https:;
      frame-ancestors 'none'
    - X-Content-Type-Options: nosniff
    - Referrer-Policy: strict-origin-when-cross-origin
    - X-Frame-Options: DENY
    - Strict-Transport-Security: max-age=31536000 (production only)

    Args:
        production: Optional boolean override for production gating.

    Returns:
        dict[str, str]: Mapping of HTTP security headers.
    """
    prod = is_production_mode() if production is None else production
    headers: dict[str, str] = {
        "Content-Security-Policy": (
            "default-src 'self'; img-src 'self' data: https:; frame-ancestors 'none'"
        ),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Frame-Options": "DENY",
    }
    if prod:
        headers["Strict-Transport-Security"] = "max-age=31536000"
    return headers


def apply_security_headers(
    headers: dict[str, str] | None = None,
    production: bool | None = None,
) -> dict[str, str]:
    """Merge security headers onto a response header dictionary.

    Args:
        headers: Optional existing header dictionary.
        production: Optional production mode override.

    Returns:
        dict[str, str]: New dictionary containing merged security headers.
    """
    base = get_security_headers(production=production)
    if headers:
        base.update(headers)
    return base


# --- Log Redaction & Filtering (docs/SECURITY.md §7, docs/CODING_STANDARDS.md §7) ---

# Sensitive field names that must have their values replaced with [REDACTED]
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "password_hash",
        "smtp_password",
        "secret_key",
        "api_key",
        "twelve_data_api_key",
        "llm_api_key",
        "token",
        "raw_token",
        "session_token",
        "reset_token",
        "verify_token",
        "csrf_token",
        "token_hash",
        "email_body",
        "chat_text",
    }
)

# Regex patterns for scrubbing secrets from strings
_REGEX_REPLACEMENTS = [
    # Argon2id password hash pattern
    (re.compile(r"\$argon2id\$[^\s\'\"]+"), "[REDACTED]"),
    # Bearer auth tokens
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.~+/]+=*"), "Bearer [REDACTED]"),
    # ot_session and ot_csrf cookies in Cookie or Set-Cookie headers
    (re.compile(r"\bot_session=[^;\s\'\"]+"), "ot_session=[REDACTED]"),
    (re.compile(r"\bot_csrf=[^;\s\'\"]+"), "ot_csrf=[REDACTED]"),
    # JSON key-value pairs for sensitive keys: "password": "value"
    (
        re.compile(
            r'("?(?:'
            + "|".join(re.escape(k) for k in _SENSITIVE_KEYS)
            + r')"??\s*[:=]\s*)"(?:[^"\\]|\\.)*"',
            re.IGNORECASE,
        ),
        r'\1"[REDACTED]"',
    ),
    # Key-value pairs in query strings, CLI, or logs: key=value
    (
        re.compile(
            r"(?i)\b(" + "|".join(re.escape(k) for k in _SENSITIVE_KEYS) + r")=([^\s,;&\'\"]+)"
        ),
        r"\1=[REDACTED]",
    ),
]


def redact_secrets(text: str) -> str:
    """Sanitize secrets, passwords, tokens, and API keys from a text string.

    Args:
        text: Input string potentially containing sensitive credentials.

    Returns:
        str: Sanitized string with sensitive values replaced by [REDACTED].
    """
    if not text:
        return text

    sanitized = text
    for pattern, replacement in _REGEX_REPLACEMENTS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_data_structure(data: Any) -> Any:
    """Recursively sanitize nested dictionaries and lists."""
    if isinstance(data, dict):
        sanitized_dict: dict[Any, Any] = {}
        for key, value in data.items():
            str_key = str(key).lower()
            if str_key in _SENSITIVE_KEYS:
                sanitized_dict[key] = "[REDACTED]"
            else:
                sanitized_dict[key] = _sanitize_data_structure(value)
        return sanitized_dict
    if isinstance(data, (list, tuple)):
        sanitized_list = [
            _sanitize_data_structure(item) if not isinstance(item, str) else redact_secrets(item)
            for item in data
        ]
        return type(data)(sanitized_list)
    if isinstance(data, str):
        return redact_secrets(data)
    return data


class SecretRedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive fields from log records per docs/SECURITY.md §7."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize record msg, args, exc_text, and extra attributes.

        Always returns True so operational logs are never dropped.
        """
        # If record has args, format the message first with sanitized args, or sanitize msg
        if record.args:
            # First sanitize the args themselves
            if isinstance(record.args, dict):
                sanitized_args = _sanitize_data_structure(record.args)
            elif isinstance(record.args, tuple):
                sanitized_args = tuple(
                    redact_secrets(arg) if isinstance(arg, str) else _sanitize_data_structure(arg)
                    for arg in record.args
                )
            else:
                sanitized_args = record.args

            # Format the message safely using % before scrubbing record.msg
            try:
                if isinstance(record.msg, str):
                    formatted = record.msg % sanitized_args
                    record.msg = redact_secrets(formatted)
                    record.args = ()
                else:
                    record.args = sanitized_args
            except Exception:
                record.args = sanitized_args
                if isinstance(record.msg, str):
                    record.msg = redact_secrets(record.msg)
        elif isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)

        # Sanitize exc_text if present
        if record.exc_text:
            record.exc_text = redact_secrets(record.exc_text)

        # Sanitize extra custom attributes attached to LogRecord
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
        }
        for attr, val in list(record.__dict__.items()):
            if attr not in standard_attrs:
                str_attr = attr.lower()
                if str_attr in _SENSITIVE_KEYS:
                    record.__dict__[attr] = "[REDACTED]"
                elif isinstance(val, (dict, list, tuple)):
                    record.__dict__[attr] = _sanitize_data_structure(deepcopy(val))
                elif isinstance(val, str):
                    record.__dict__[attr] = redact_secrets(val)

        return True


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root logger with SecretRedactingFilter per docs/SECURITY.md §7.

    Args:
        level: Minimum log level string (e.g. 'DEBUG', 'INFO', 'WARNING').

    Returns:
        logging.Logger: The configured root logger.
    """
    root_logger = logging.getLogger()
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Attach SecretRedactingFilter to root logger
    redacting_filter = SecretRedactingFilter()
    root_logger.addFilter(redacting_filter)

    # Ensure existing handlers also receive the filter
    for handler in root_logger.handlers:
        handler.addFilter(redacting_filter)

    return root_logger
