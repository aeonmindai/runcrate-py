"""Exception hierarchy for the Runcrate SDK."""

from __future__ import annotations

from typing import Any, Optional

import httpx


class RuncrateError(Exception):
    """Base exception for all Runcrate SDK errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ApiError(RuncrateError):
    """Raised when the API returns a non-2xx response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str,
        details: Optional[dict[str, Any]] = None,
        response: Optional[httpx.Response] = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.details = details
        self.response = response
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(status_code={self.status_code}, code={self.code!r}, message={self.message!r})"


class BadRequestError(ApiError):
    """400 - Invalid request parameters."""


class AuthenticationError(ApiError):
    """401 - Invalid or missing API key."""


class InsufficientCreditsError(ApiError):
    """402 - Not enough credits to perform operation."""


class PermissionDeniedError(ApiError):
    """403 - User lacks permission."""


class NotFoundError(ApiError):
    """404 - Resource not found."""


class ConflictError(ApiError):
    """409 - Resource conflict (e.g., duplicate SSH key)."""


class RateLimitError(ApiError):
    """429 - Rate limit exceeded."""


class InternalServerError(ApiError):
    """500 - Server error."""


class ConnectionError(RuncrateError):
    """Network connectivity failure."""


class TimeoutError(RuncrateError):
    """Request timed out."""


_STATUS_MAP: dict[int, type[ApiError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    402: InsufficientCreditsError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
    500: InternalServerError,
}


def make_api_error(response: httpx.Response) -> ApiError:
    """Create the appropriate ApiError subclass from an HTTP response."""
    try:
        body = response.json()
        err = body.get("error", {})
        code = err.get("code", "unknown")
        message = err.get("message", response.text)
        details = err.get("details")
    except Exception:
        code = "unknown"
        message = response.text or f"HTTP {response.status_code}"
        details = None

    cls = _STATUS_MAP.get(response.status_code, ApiError)
    return cls(
        message,
        status_code=response.status_code,
        code=code,
        details=details,
        response=response,
    )
