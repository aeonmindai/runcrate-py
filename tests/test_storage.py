"""Tests for storage resource."""

from __future__ import annotations

import httpx
import respx

from runcrate import Runcrate


class TestStorage:
    def test_list_volumes(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/storage").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "v1",
                            "name": "datasets",
                            "sizeGb": 100,
                            "status": "available",
                            "region": "us-east",
                        }
                    ]
                },
            )
        )

        volumes = client.storage.list()
        assert len(volumes) == 1
        assert volumes[0].id == "v1"
        assert volumes[0].name == "datasets"
        assert volumes[0].size_gb == 100

    def test_list_volumes_with_search(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/storage").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        client.storage.list(search="data")
        assert route.calls[0].request.url.params["search"] == "data"

    def test_get_volume(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/storage/v1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "v1",
                        "name": "datasets",
                        "sizeGb": 100,
                        "status": "attached",
                        "deploymentId": "inst-1",
                    }
                },
            )
        )

        volume = client.storage.get("v1")
        assert volume.id == "v1"
        assert volume.status == "attached"
        assert volume.deployment_id == "inst-1"
