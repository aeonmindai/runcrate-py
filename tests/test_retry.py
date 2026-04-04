"""Tests for retry and error handling."""

from __future__ import annotations

import httpx
import pytest
import respx

from runcrate import Runcrate, RateLimitError, InternalServerError


class TestRetry:
    def test_retries_on_500(self, api_key: str, base_url: str, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/instances").mock(
            side_effect=[
                httpx.Response(500, json={"error": {"code": "internal_error", "message": "oops"}}),
                httpx.Response(200, json={"data": []}),
            ]
        )

        client = Runcrate(api_key=api_key, base_url=base_url, max_retries=1)
        result = client.instances.list()
        assert result == []
        assert route.call_count == 2
        client.close()

    def test_no_retry_when_disabled(self, api_key: str, base_url: str, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances").mock(
            return_value=httpx.Response(
                500, json={"error": {"code": "internal_error", "message": "oops"}}
            )
        )

        client = Runcrate(api_key=api_key, base_url=base_url, max_retries=0)
        with pytest.raises(InternalServerError):
            client.instances.list()
        client.close()

    def test_rate_limit_error(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances").mock(
            return_value=httpx.Response(
                429,
                json={"error": {"code": "rate_limited", "message": "Too many requests"}},
                headers={"Retry-After": "60"},
            )
        )

        with pytest.raises(RateLimitError) as exc_info:
            client.instances.list()
        assert exc_info.value.status_code == 429

    def test_no_retry_on_400(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.post("/api/v1/instances").mock(
            return_value=httpx.Response(
                400,
                json={"error": {"code": "bad_request", "message": "Missing name"}},
            )
        )

        from runcrate import BadRequestError

        with pytest.raises(BadRequestError):
            client.instances.create(name="", ssh_key_id="key")
        assert route.call_count == 1
