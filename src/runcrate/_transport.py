"""HTTP transport layer with retry logic and response parsing."""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import TypeAdapter

from runcrate._config import ClientConfig
from runcrate._exceptions import (
    ApiError,
    ConnectionError,
    TimeoutError,
    make_api_error,
)

T = TypeVar("T")

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# The statuses that say a request was not acted on: rate limited before the handler ran (429), or
# refused for no capacity before anything was created (503). The only statuses a request that is
# not safe to send twice is retried on.
_NOT_ACTED_ON_STATUS_CODES = {429, 503}
# How long a retry waits at least while the server still handles the same Idempotency-Key.
_IN_PROGRESS_MIN_DELAY = 3.0
_BASE_DELAY = 0.5
_MAX_DELAY = 30.0
_JITTER_FACTOR = 0.25
# The longest a Retry-After header is honoured, in seconds: a server asking for more is capped.
_MAX_RETRY_AFTER = 60.0
# Error codes never retried, whatever their status: the same request fails the same way.
# launch_refused (502): the machine was refused for the request itself, not for capacity.
_NON_RETRYABLE_CODES = {"launch_refused"}

# Seconds a launch (instance create, schedule run-now) gets at least: the route may take 60 s.
LAUNCH_TIMEOUT = 75.0


def new_idempotency_key() -> str:
    """A fresh Idempotency-Key: one per call, sent again on each of that call's retries."""
    return str(uuid.uuid4())


def _backoff_delay(attempt: int, retry_after: Optional[float] = None) -> float:
    if retry_after is not None:
        return min(max(retry_after, 0.0), _MAX_RETRY_AFTER)
    delay = min(_BASE_DELAY * (2**attempt), _MAX_DELAY)
    jitter = delay * _JITTER_FACTOR * random.random()
    return delay + jitter


def _parse_retry_after(response: httpx.Response) -> Optional[float]:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _error_info(response: httpx.Response) -> tuple[Optional[str], Optional[str]]:
    """The API error code and ``details.reason`` of a JSON error response, if it has them."""
    if "application/json" not in response.headers.get("content-type", ""):
        return None, None
    try:
        body = response.json()
    except ValueError:
        return None, None
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return None, None
    code = error.get("code")
    details = error.get("details")
    reason = details.get("reason") if isinstance(details, dict) else None
    return (
        code if isinstance(code, str) else None,
        reason if isinstance(reason, str) else None,
    )


def _response_retry_delay(
    response: httpx.Response,
    attempt: int,
    max_retries: int,
    *,
    idempotent: bool,
    idempotency_key: Optional[str],
) -> Optional[float]:
    """Seconds to wait before sending the request again, or None to answer this response."""
    status = response.status_code
    if attempt >= max_retries or (status not in _RETRYABLE_STATUS_CODES and status != 409):
        return None
    code, reason = _error_info(response)
    retry_after = _parse_retry_after(response)
    if status == 409:
        # The first request with this key is still being handled: ask again for its result.
        if idempotency_key and reason == "idempotency_in_progress":
            return max(_backoff_delay(attempt, retry_after), _IN_PROGRESS_MIN_DELAY)
        return None
    if code in _NON_RETRYABLE_CODES:
        return None
    if not idempotent and status not in _NOT_ACTED_ON_STATUS_CODES:
        return None
    return _backoff_delay(attempt, retry_after)


def _error_retry_delay(
    exc: httpx.TransportError, attempt: int, max_retries: int, *, idempotent: bool
) -> Optional[float]:
    """Seconds to wait before sending again after no response came, or None to raise.

    A request that may have reached the server is only sent again when that is harmless; one
    whose connection never opened (ConnectError, ConnectTimeout) cannot have been seen.
    """
    if attempt >= max_retries:
        return None
    if idempotent or isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return _backoff_delay(attempt)
    return None


def _as_sdk_error(exc: httpx.TransportError) -> Exception:
    if isinstance(exc, httpx.TimeoutException):
        return TimeoutError(f"Request timed out: {exc}")
    return ConnectionError(f"Connection failed: {exc}")


def _parse_response(response: httpx.Response, cast_to: Optional[Type[T]]) -> Any:
    if response.status_code == 204:
        return None

    if response.status_code >= 400:
        raise make_api_error(response)

    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        raise ApiError(
            f"Expected JSON response but got {content_type!r} (status {response.status_code}). "
            f"Check that base_url is correct. Response: {response.text[:200]}",
            status_code=response.status_code,
            code="invalid_response",
            response=response,
        )

    try:
        body = response.json()
    except Exception as e:
        raise ApiError(
            f"Failed to parse JSON response: {e}. Response: {response.text[:200]}",
            status_code=response.status_code,
            code="invalid_response",
            response=response,
        ) from e

    data = body.get("data", body)
    meta = body.get("meta")

    if cast_to is None:
        return data

    adapter = TypeAdapter(cast_to)
    parsed = adapter.validate_python(data)
    return parsed, meta


def _redirect_location(response: httpx.Response) -> str:
    """Where a redirect points; the API error otherwise."""
    location = response.headers.get("location")
    if 300 <= response.status_code < 400 and location:
        return str(response.url.join(location))
    if response.status_code >= 400:
        raise make_api_error(response)
    raise ApiError(
        f"Expected a redirect, got HTTP {response.status_code}",
        status_code=response.status_code,
        code="invalid_response",
        response=response,
    )


class _RequestPlan:
    """What one call sends on every attempt, and whether sending it twice is harmless."""

    def __init__(
        self,
        config: ClientConfig,
        method: str,
        *,
        params: Optional[dict[str, Any]],
        timeout: Optional[float],
        min_timeout: Optional[float],
        idempotency_key: Optional[str],
        idempotent: Optional[bool],
    ) -> None:
        if config.environment:
            params = {"environment": config.environment, **(params or {})}
        self.params = params
        self.timeout = max(timeout if timeout is not None else config.timeout, min_timeout or 0.0)
        self.headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        self.idempotency_key = idempotency_key
        # GET, PATCH, PUT and DELETE are safe to repeat; a POST only when its route dedupes it.
        self.idempotent = idempotent if idempotent is not None else method.upper() != "POST"


def _client_headers(config: ClientConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "User-Agent": "runcrate-python/0.1.0",
        **config.custom_headers,
    }


class SyncTransport:
    """Synchronous HTTP transport with retry and rate-limit handling.

    ``idempotent`` says whether sending a request twice is harmless (default: everything but
    POST). A request that is not is never sent again once it may have reached the server (a
    timeout, a lost connection, a 500, 502 or 504): only a 429 or 503, which say nothing was done,
    and a connection that never opened are retried. ``idempotency_key`` is sent as the
    Idempotency-Key header on every attempt of the call.
    """

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers=_client_headers(config),
            timeout=config.timeout,
        )

    def send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        min_timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        idempotent: Optional[bool] = None,
    ) -> httpx.Response:
        """Sends the request with retries and answers the last response (redirects not followed)."""
        plan = _RequestPlan(
            self._config,
            method,
            params=params,
            timeout=timeout,
            min_timeout=min_timeout,
            idempotency_key=idempotency_key,
            idempotent=idempotent,
        )
        max_retries = self._config.max_retries
        for attempt in range(max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    params=plan.params,
                    json=json,
                    headers=plan.headers,
                    timeout=plan.timeout,
                )
            except httpx.TransportError as e:
                delay = _error_retry_delay(e, attempt, max_retries, idempotent=plan.idempotent)
                if delay is None:
                    raise _as_sdk_error(e) from e
                time.sleep(delay)
                continue

            delay = _response_retry_delay(
                response,
                attempt,
                max_retries,
                idempotent=plan.idempotent,
                idempotency_key=plan.idempotency_key,
            )
            if delay is None:
                return response
            time.sleep(delay)

        raise RuntimeError("Unexpected retry exhaustion")

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        cast_to: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
        min_timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        idempotent: Optional[bool] = None,
    ) -> Any:
        response = self.send(
            method,
            path,
            params=params,
            json=json,
            timeout=timeout,
            min_timeout=min_timeout,
            idempotency_key=idempotency_key,
            idempotent=idempotent,
        )
        return _parse_response(response, cast_to)

    def redirect_location(self, path: str) -> str:
        """Where a redirecting GET (an artifact download) points, without following it."""
        return _redirect_location(self.send("GET", path))

    def close(self) -> None:
        self._client.close()


class AsyncTransport:
    """Asynchronous HTTP transport with retry and rate-limit handling. See ``SyncTransport``."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=_client_headers(config),
            timeout=config.timeout,
        )

    async def send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        min_timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        idempotent: Optional[bool] = None,
    ) -> httpx.Response:
        """Sends the request with retries and answers the last response (redirects not followed)."""
        plan = _RequestPlan(
            self._config,
            method,
            params=params,
            timeout=timeout,
            min_timeout=min_timeout,
            idempotency_key=idempotency_key,
            idempotent=idempotent,
        )
        max_retries = self._config.max_retries
        for attempt in range(max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=plan.params,
                    json=json,
                    headers=plan.headers,
                    timeout=plan.timeout,
                )
            except httpx.TransportError as e:
                delay = _error_retry_delay(e, attempt, max_retries, idempotent=plan.idempotent)
                if delay is None:
                    raise _as_sdk_error(e) from e
                await asyncio.sleep(delay)
                continue

            delay = _response_retry_delay(
                response,
                attempt,
                max_retries,
                idempotent=plan.idempotent,
                idempotency_key=plan.idempotency_key,
            )
            if delay is None:
                return response
            await asyncio.sleep(delay)

        raise RuntimeError("Unexpected retry exhaustion")

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        cast_to: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
        min_timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        idempotent: Optional[bool] = None,
    ) -> Any:
        response = await self.send(
            method,
            path,
            params=params,
            json=json,
            timeout=timeout,
            min_timeout=min_timeout,
            idempotency_key=idempotency_key,
            idempotent=idempotent,
        )
        return _parse_response(response, cast_to)

    async def redirect_location(self, path: str) -> str:
        """Where a redirecting GET (an artifact download) points, without following it."""
        return _redirect_location(await self.send("GET", path))

    async def close(self) -> None:
        await self._client.aclose()
