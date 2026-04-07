"""Tests for templates resource."""

from __future__ import annotations

import httpx
import respx

from runcrate import Runcrate, PaginatedResponse


class TestTemplates:
    def test_list_templates(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/templates").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "tpl1", "name": "Ubuntu CUDA", "category": "ml"},
                        {"id": "tpl2", "name": "PyTorch", "category": "ml"},
                    ],
                    "meta": {"hasMore": False, "total": 2},
                },
            )
        )

        result = client.templates.list()
        assert isinstance(result, PaginatedResponse)
        assert len(result.data) == 2
        assert result.data[0].name == "Ubuntu CUDA"
        assert result.has_more is False
        assert result.total == 2

    def test_list_templates_with_search(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/templates").mock(
            return_value=httpx.Response(200, json={"data": [], "meta": {}})
        )

        client.templates.list(search="pytorch", category="ml")
        params = route.calls[0].request.url.params
        assert params["search"] == "pytorch"
        assert params["category"] == "ml"

    def test_list_templates_pagination(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/templates").mock(
            return_value=httpx.Response(200, json={"data": [], "meta": {}})
        )

        client.templates.list(page=2, page_size=10)
        params = route.calls[0].request.url.params
        assert params["page"] == "2"
        assert params["page_size"] == "10"

    def test_list_templates_iterable(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/templates").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "tpl1", "name": "A"},
                        {"id": "tpl2", "name": "B"},
                    ],
                    "meta": {},
                },
            )
        )

        result = client.templates.list()
        names = [t.name for t in result]
        assert names == ["A", "B"]
