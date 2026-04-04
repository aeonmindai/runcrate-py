"""Pagination helpers."""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from runcrate.models.shared import ListMeta

T = TypeVar("T")


class PaginatedResponse(Generic[T]):
    """A single page of results with metadata."""

    def __init__(self, data: List[T], meta: Optional[ListMeta] = None) -> None:
        self.data = data
        self.meta = meta or ListMeta()

    @property
    def has_more(self) -> bool:
        return self.meta.has_more or False

    @property
    def cursor(self) -> Optional[str]:
        return self.meta.cursor

    @property
    def total(self) -> Optional[int]:
        return self.meta.total

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return f"PaginatedResponse(count={len(self.data)}, has_more={self.has_more}, total={self.total})"
