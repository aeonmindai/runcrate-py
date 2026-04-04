"""HTTP transport layer with retry logic and response parsing."""

from __future__ import annotations

import random
import time
from typing import Any, Generic, Optional, Type, TypeVar, Union, overload

import httpx
from pydantic import BaseModel, TypeAdapter

from runcrate._config import ClientConfig
from runcrate._exceptions import (
    ConnectionError,
    RateLimitError,
    TimeoutError,
    make_api_error,
)

T = TypeVar("T")

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_BASE_DELAY = 0.5
_MAX_DELAY = 30.0
_JITTER_FACTOR = 0.25


def _backoff_delay(attempt: int, retry_after: Optional[float] = None) -> float:
    if retry_after is not None:
        return retry_after
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


def _parse_response(response: httpx.Response, cast_to: Optional[Type[T]]) -> Any:
    if response.status_code == 204:
        return None

    if response.status_code >= 400:
        raise make_api_error(response)

    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        from runcrate._exceptions import ApiError

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
        from runcrate._exceptions import ApiError

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


class SyncTransport:
    """Synchronous HTTP transport with retry and rate-limit handling."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "runcrate-python/0.1.0",
                **config.custom_headers,
            },
            timeout=config.timeout,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        cast_to: Optional[Type[T]] = None,
    ) -> Any:
        last_exc: Optional[Exception] = None

        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._client.request(
                    method, path, params=params, json=json
                )
            except httpx.TimeoutException as e:
                last_exc = TimeoutError(f"Request timed out: {e}")
                if attempt < self._config.max_retries:
                    time.sleep(_backoff_delay(attempt))
                    continue
                raise last_exc from e
            except httpx.TransportError as e:
                last_exc = ConnectionError(f"Connection failed: {e}")
                if attempt < self._config.max_retries:
                    time.sleep(_backoff_delay(attempt))
                    continue
                raise last_exc from e

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._config.max_retries:
                retry_after = _parse_retry_after(response)
                time.sleep(_backoff_delay(attempt, retry_after))
                continue

            return _parse_response(response, cast_to)

        raise last_exc or RuntimeError("Unexpected retry exhaustion")

    def close(self) -> None:
        self._client.close()


class AsyncTransport:
    """Asynchronous HTTP transport with retry and rate-limit handling."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "runcrate-python/0.1.0",
                **config.custom_headers,
            },
            timeout=config.timeout,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        cast_to: Optional[Type[T]] = None,
    ) -> Any:
        import asyncio

        last_exc: Optional[Exception] = None

        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._client.request(
                    method, path, params=params, json=json
                )
            except httpx.TimeoutException as e:
                last_exc = TimeoutError(f"Request timed out: {e}")
                if attempt < self._config.max_retries:
                    await asyncio.sleep(_backoff_delay(attempt))
                    continue
                raise last_exc from e
            except httpx.TransportError as e:
                last_exc = ConnectionError(f"Connection failed: {e}")
                if attempt < self._config.max_retries:
                    await asyncio.sleep(_backoff_delay(attempt))
                    continue
                raise last_exc from e

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._config.max_retries:
                retry_after = _parse_retry_after(response)
                await asyncio.sleep(_backoff_delay(attempt, retry_after))
                continue

            return _parse_response(response, cast_to)

        raise last_exc or RuntimeError("Unexpected retry exhaustion")

    async def close(self) -> None:
        await self._client.aclose()
