"""Tests for projects resource."""

from __future__ import annotations

import httpx
import respx

from runcrate import Runcrate


class TestProjects:
    def test_list_projects(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/projects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "p1", "name": "ML Research", "is_default": True},
                        {"id": "p2", "name": "Production", "is_default": False},
                    ]
                },
            )
        )

        projects = client.projects.list()
        assert len(projects) == 2
        assert projects[0].id == "p1"
        assert projects[0].name == "ML Research"
        assert projects[0].is_default is True

    def test_create_project(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/projects").mock(
            return_value=httpx.Response(
                201,
                json={
                    "data": {
                        "id": "p-new",
                        "name": "New Project",
                        "description": "Testing",
                        "is_default": False,
                    }
                },
            )
        )

        project = client.projects.create(name="New Project", description="Testing")
        assert project.id == "p-new"
        assert project.name == "New Project"
        assert project.description == "Testing"

    def test_get_project(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/projects/p1").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"id": "p1", "name": "ML Research"}},
            )
        )

        project = client.projects.get("p1")
        assert project.id == "p1"

    def test_update_project(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.patch("/api/v1/projects/p1").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"id": "p1", "name": "Renamed"}},
            )
        )

        project = client.projects.update("p1", name="Renamed")
        assert project.name == "Renamed"

    def test_delete_project(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.delete("/api/v1/projects/p1").mock(
            return_value=httpx.Response(204)
        )

        client.projects.delete("p1")  # should not raise
