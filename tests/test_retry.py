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

    def test_no_retry_on_launch_refused(self, api_key: str, base_url: str, mock_api: respx.MockRouter):
        message = "The machine could not be created (request_conflict)."
        route = mock_api.post("/api/v1/instances").mock(
            side_effect=[
                httpx.Response(502, json={"error": {"code": "launch_refused", "message": message}}),
                httpx.Response(201, json={"data": {}}),
            ]
        )

        from runcrate import ApiError

        client = Runcrate(api_key=api_key, base_url=base_url, max_retries=2)
        with pytest.raises(ApiError) as exc_info:
            client.instances.create(name="box", ssh_key_id="key")
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "launch_refused"
        assert route.call_count == 1, "the same request is refused the same way"
        client.close()

    async def test_async_no_retry_on_launch_refused(self, api_key: str, base_url: str, mock_api: respx.MockRouter):
        route = mock_api.post("/api/v1/instances").mock(
            side_effect=[
                httpx.Response(502, json={"error": {"code": "launch_refused", "message": "refused"}}),
                httpx.Response(201, json={"data": {}}),
            ]
        )

        from runcrate import ApiError, AsyncRuncrate

        client = AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=2)
        with pytest.raises(ApiError):
            await client.instances.create(name="box", ssh_key_id="key")
        assert route.call_count == 1
        await client.close()

    def test_retry_after_is_capped_at_60_seconds(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
    ):
        slept: list[float] = []
        monkeypatch.setattr("runcrate._transport.time.sleep", slept.append)
        route = mock_api.get("/api/v1/instances").mock(
            side_effect=[
                httpx.Response(503, json={"error": {"code": "service_unavailable", "message": "No GPU"}}, headers={"Retry-After": "3600"}),
                httpx.Response(503, json={"error": {"code": "service_unavailable", "message": "No GPU"}}, headers={"Retry-After": "7"}),
                httpx.Response(200, json={"data": []}),
            ]
        )

        client = Runcrate(api_key=api_key, base_url=base_url, max_retries=2)
        assert client.instances.list() == []
        assert slept == [60.0, 7.0]
        assert route.call_count == 3
        client.close()
