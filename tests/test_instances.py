"""Tests for instances resource."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from runcrate import AsyncRuncrate, InsufficientCreditsError, NotFoundError, Runcrate


class TestInstances:
    def test_list_instances(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "inst-1",
                            "name": "test-gpu",
                            "status": "running",
                            "gpu_type": "A100",
                            "gpu_count": 1,
                            "region": "us-east",
                            "ip": "1.2.3.4",
                            "cost_per_hour": 2.50,
                        }
                    ]
                },
            )
        )

        instances = client.instances.list()
        assert len(instances) == 1
        assert instances[0].id == "inst-1"
        assert instances[0].name == "test-gpu"
        assert instances[0].status == "running"
        assert instances[0].gpu_type == "A100"
        assert instances[0].cost_per_hour == 2.50

    def test_list_instances_with_search(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/instances").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        client.instances.list(search="my-gpu")
        assert route.calls[0].request.url.params["search"] == "my-gpu"

    def test_create_instance(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/instances").mock(
            return_value=httpx.Response(
                201,
                json={
                    "data": {
                        "id": "inst-new",
                        "name": "training",
                        "status": "deploying",
                        "gpu_type": "A100",
                        "gpu_count": 2,
                    }
                },
            )
        )

        instance = client.instances.create(
            name="training",
            ssh_key_id="key-1",
            gpu_type="A100",
            gpu_count=2,
        )
        assert instance.id == "inst-new"
        assert instance.status == "deploying"
        assert instance.gpu_count == 2

    def test_get_instance(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances/inst-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "inst-1",
                        "name": "test",
                        "status": "running",
                    }
                },
            )
        )

        instance = client.instances.get("inst-1")
        assert instance.id == "inst-1"

    def test_terminate_instance(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.delete("/api/v1/instances/inst-1").mock(
            return_value=httpx.Response(204)
        )

        client.instances.terminate("inst-1")  # should not raise

    def test_get_status(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances/inst-1/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "inst-1",
                        "status": "running",
                        "ip": "10.0.0.1",
                    }
                },
            )
        )

        status = client.instances.get_status("inst-1")
        assert status.status == "running"
        assert status.ip == "10.0.0.1"

    def test_list_types(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances/types").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "bold-tesla-a100-fa6f",
                            "gpu_type": "A100",
                            "gpu_count": 1,
                            "cpu_cores": 8,
                            "memory_gb": 32.0,
                            "storage_gb": 100.0,
                            "region": "us-east",
                            "hourly_rate": 2.50,
                        }
                    ],
                    "meta": {"total": 1},
                },
            )
        )

        types = client.instances.list_types(gpu_type="A100")
        assert len(types) == 1
        assert types[0].hourly_rate == 2.50

    def test_not_found_error(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances/nonexistent").mock(
            return_value=httpx.Response(
                404,
                json={
                    "error": {
                        "code": "not_found",
                        "message": "Instance not found",
                    }
                },
            )
        )

        try:
            client.instances.get("nonexistent")
            assert False, "Should have raised NotFoundError"
        except NotFoundError as e:
            assert e.status_code == 404
            assert e.code == "not_found"
            assert "not found" in e.message.lower()


_CREATED = {"data": {"id": "inst-new", "name": "agent-run", "status": "deploying"}}


class TestInstanceGuardrails:
    def test_create_sends_guardrails(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.post("/api/v1/instances").mock(
            return_value=httpx.Response(201, json=_CREATED)
        )

        client.instances.create(
            name="agent-run",
            ssh_key_id="key-1",
            gpu_type="H100",
            max_runtime_minutes=240,
            idle_shutdown_minutes=30,
        )

        body = json.loads(route.calls[0].request.content)
        assert body["max_runtime_minutes"] == 240
        assert body["idle_shutdown_minutes"] == 30

    def test_create_omits_unset_guardrails(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.post("/api/v1/instances").mock(
            return_value=httpx.Response(201, json=_CREATED)
        )

        client.instances.create(name="agent-run", ssh_key_id="key-1", gpu_type="H100")

        body = json.loads(route.calls[0].request.content)
        assert "max_runtime_minutes" not in body
        assert "idle_shutdown_minutes" not in body

    async def test_async_create_sends_guardrails(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter
    ):
        route = mock_api.post("/api/v1/instances").mock(
            return_value=httpx.Response(201, json=_CREATED)
        )

        async with AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=0) as client:
            await client.instances.create(
                name="agent-run", ssh_key_id="key-1", max_runtime_minutes=60
            )

        body = json.loads(route.calls[0].request.content)
        assert body["max_runtime_minutes"] == 60
        assert "idle_shutdown_minutes" not in body

    def test_get_parses_guardrail_fields(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/instances/inst-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "inst-1",
                        "name": "agent-run",
                        "status": "stopped",
                        "max_runtime_minutes": 240,
                        "idle_shutdown_minutes": 30,
                        "auto_stop_at": "2026-10-20T16:00:00Z",
                        "stop_reason": "idle",
                    }
                },
            )
        )

        instance = client.instances.get("inst-1")
        assert instance.max_runtime_minutes == 240
        assert instance.idle_shutdown_minutes == 30
        assert instance.auto_stop_at == datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
        assert instance.stop_reason == "idle"

    def test_get_parses_payload_without_guardrail_fields(
        self, client: Runcrate, mock_api: respx.MockRouter
    ):
        mock_api.get("/api/v1/instances/inst-1").mock(
            return_value=httpx.Response(
                200, json={"data": {"id": "inst-1", "name": "old", "status": "running"}}
            )
        )

        instance = client.instances.get("inst-1")
        assert instance.max_runtime_minutes is None
        assert instance.idle_shutdown_minutes is None
        assert instance.auto_stop_at is None
        assert instance.stop_reason is None

    def test_budget_reached_surfaces_code(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/instances").mock(
            return_value=httpx.Response(
                402,
                json={
                    "error": {
                        "code": "BUDGET_REACHED",
                        "message": "This environment reached its $500.00 monthly budget.",
                    }
                },
            )
        )

        with pytest.raises(InsufficientCreditsError) as exc:
            client.instances.create(name="agent-run", ssh_key_id="key-1")
        assert exc.value.status_code == 402
        assert exc.value.code == "BUDGET_REACHED"
        assert "monthly budget" in exc.value.message
