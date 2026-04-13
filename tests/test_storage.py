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

    def test_list_regions(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/storage/regions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "137", "name": "us-east-1", "provider": "aws-s3"},
                        {"id": "21", "name": "us-west-1", "provider": "wasabi"},
                    ]
                },
            )
        )

        regions = client.storage.list_regions()
        assert len(regions) == 2
        assert regions[0].id == "137"
        assert regions[0].name == "us-east-1"
        assert regions[0].provider == "aws-s3"

    def test_create_volume(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.post("/api/v1/storage").mock(
            return_value=httpx.Response(
                201,
                json={
                    "data": {
                        "id": "v1",
                        "name": "datasets",
                        "size_gb": 100,
                        "status": "active",
                        "region": "137",
                    }
                },
            )
        )

        volume = client.storage.create(name="datasets", size_gb=100, region="us-east-1")
        assert volume.id == "v1"
        assert volume.size_gb == 100

        body = route.calls[0].request.content.decode()
        assert '"name":"datasets"' in body
        assert '"size_gb":100' in body
        assert '"region":"us-east-1"' in body

    def test_resize_volume(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.patch("/api/v1/storage/v1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "v1",
                        "name": "datasets",
                        "size_gb": 200,
                        "status": "active",
                    }
                },
            )
        )

        volume = client.storage.resize("v1", size_gb=200)
        assert volume.size_gb == 200

        body = route.calls[0].request.content.decode()
        assert '"size_gb":200' in body

    def test_delete_volume(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.delete("/api/v1/storage/v1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "message": "Storage volume deleted successfully",
                        "refund_amount": 0.42,
                    }
                },
            )
        )

        result = client.storage.delete("v1")
        assert result.message == "Storage volume deleted successfully"
        assert result.refund_amount == 0.42
        assert route.called
