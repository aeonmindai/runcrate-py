"""Tests for pagination helpers."""

from __future__ import annotations

from runcrate._pagination import PaginatedResponse
from runcrate.models.shared import ListMeta


class TestPaginatedResponse:
    def test_wraps_data(self):
        response = PaginatedResponse(data=[1, 2, 3])
        assert response.data == [1, 2, 3]
        assert len(response) == 3

    def test_exposes_meta(self):
        meta = ListMeta(has_more=True, total=50, cursor="abc")
        response = PaginatedResponse(data=[{"id": "1"}], meta=meta)
        assert response.has_more is True
        assert response.total == 50
        assert response.cursor == "abc"

    def test_defaults_has_more_false(self):
        response = PaginatedResponse(data=[])
        assert response.has_more is False
        assert response.total is None
        assert response.cursor is None

    def test_is_iterable(self):
        items = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        response = PaginatedResponse(data=items)
        collected = list(response)
        assert collected == items

    def test_repr(self):
        response = PaginatedResponse(
            data=[1, 2],
            meta=ListMeta(has_more=True, total=10),
        )
        r = repr(response)
        assert "count=2" in r
        assert "has_more=True" in r
        assert "total=10" in r
