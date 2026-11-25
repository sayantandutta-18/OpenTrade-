"""Typed exception definitions mapped to API error codes in docs/API_SPEC.md."""

import uuid


class AppError(Exception):
    """Base application exception with error code, HTTP status, and request ID."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL",
        status_code: int = 500,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id or str(uuid.uuid4())

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Format error response dictionary matching docs/API_SPEC.md conventions."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
            }
        }


class ValidationError(AppError):
    """Input did not pass validation rules (HTTP 422)."""

    def __init__(
        self,
        message: str,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_FAILED",
            status_code=422,
            request_id=request_id,
        )


class WeakPasswordError(AppError):
    """Password strength or uniqueness rule failed (HTTP 422)."""

    def __init__(
        self,
        message: str,
        code: str = "WEAK_PASSWORD",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=422,
            request_id=request_id,
        )


class EmailTakenError(AppError):
    """Registration email already exists (HTTP 409)."""

    def __init__(
        self,
        message: str = "Email is already taken",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EMAIL_TAKEN",
            status_code=409,
            request_id=request_id,
        )


class UnauthenticatedError(AppError):
    """No valid session or authentication token (HTTP 401)."""

    def __init__(
        self,
        message: str = "Authentication required",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UNAUTHENTICATED",
            status_code=401,
            request_id=request_id,
        )


class NotFoundError(AppError):
    """Resource not found or belongs to another user (HTTP 404)."""

    def __init__(
        self,
        message: str = "Not found",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            request_id=request_id,
        )


class AccountLockedError(AppError):
    """Account is locked due to too many failed login attempts (HTTP 423)."""

    def __init__(
        self,
        message: str = "Account is locked. Please try again later.",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ACCOUNT_LOCKED",
            status_code=423,
            request_id=request_id,
        )


class TokenInvalidError(AppError):
    """Token is invalid, used, or expired (HTTP 400)."""

    def __init__(
        self,
        message: str = "Invalid or expired token",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="TOKEN_INVALID",
            status_code=400,
            request_id=request_id,
        )


class RateLimitedError(AppError):
    """Rate limit exceeded for the requested operation (HTTP 429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RATE_LIMITED",
            status_code=429,
            request_id=request_id,
        )


class CsrfFailedError(AppError):
    """Missing or invalid CSRF token on state-changing request (HTTP 403)."""

    def __init__(
        self,
        message: str = "Missing or wrong CSRF token",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CSRF_FAILED",
            status_code=403,
            request_id=request_id,
        )
