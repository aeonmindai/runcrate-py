"""Tests for the secrets resource: names only, in the client's environment."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from runcrate import AsyncRuncrate, Runcrate

ANSWER = {
    "data": [
        # A value the API should never send is dropped all the same.
        {"key": "DB_URL", "sensitive": True, "updated_at": "2026-10-20T11:00:00Z", "value": "postgres://leak"},
        {"key": "HF_TOKEN", "sensitive": False, "updated_at": "2026-10-21T09:30:00Z"},
    ]
}


class TestSecrets:
    def test_list_reads_the_environment_and_returns_names_only(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter
    ):
        route = mock_api.get("/api/v1/secrets").mock(return_value=httpx.Response(200, json=ANSWER))
        with Runcrate(api_key=api_key, base_url=base_url, max_retries=0, environment="staging") as client:
            secrets = client.secrets.list()

        assert route.call_count == 1
        assert route.calls[0].request.url.params["environment"] == "staging"
        assert [(s.key, s.sensitive) for s in secrets] == [("DB_URL", True), ("HF_TOKEN", False)]
        assert secrets[1].updated_at == datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc)
        assert "postgres" not in repr(secrets) and "postgres" not in str([s.model_dump() for s in secrets])

    @pytest.mark.asyncio
    async def test_async_list(self, api_key: str, base_url: str, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/secrets").mock(return_value=httpx.Response(200, json=ANSWER))
        async with AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=0) as client:
            secrets = await client.secrets.list()

        assert [s.key for s in secrets] == ["DB_URL", "HF_TOKEN"]
        assert all(not hasattr(s, "value") for s in secrets)
