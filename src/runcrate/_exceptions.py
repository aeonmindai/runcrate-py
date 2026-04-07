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


class UnprocessableEntityError(ApiError):
    """422 - Validation error (e.g., invalid model parameters)."""


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
    422: UnprocessableEntityError,
    429: RateLimitError,
    500: InternalServerError,
}


def _extract_error_info(body: Any) -> tuple[Optional[str], str, Optional[dict[str, Any]]]:
    """Extract message, code, and details from various error response formats."""
    if not isinstance(body, dict):
        return None, "api_error", None

    # Format: { error: { code, message, details } }
    err = body.get("error")
    if isinstance(err, dict):
        return (
            err.get("message"),
            err.get("code", "api_error"),
            err.get("details"),
        )

    # Format: { error: "string message" }
    if isinstance(err, str):
        return err, "api_error", None

    # Format: { message: "string" }
    if isinstance(body.get("message"), str):
        return body["message"], body.get("code", "api_error"), None

    # Format: { detail: "string" } (FastAPI style)
    if isinstance(body.get("detail"), str):
        return body["detail"], "api_error", None

    return None, "api_error", None


def make_api_error(response: httpx.Response) -> ApiError:
    """Create the appropriate ApiError subclass from an HTTP response."""
    try:
        body = response.json()
    except Exception:
        body = None

    extracted_message, code, details = _extract_error_info(body)

    # Fallback: use raw response text if we couldn't extract a message
    if extracted_message is None:
        text = response.text or ""
        extracted_message = text[:500] if text else f"HTTP {response.status_code}"

    cls = _STATUS_MAP.get(response.status_code, ApiError)
    return cls(
        extracted_message,
        status_code=response.status_code,
        code=code,
        details=details,
        response=response,
    )
