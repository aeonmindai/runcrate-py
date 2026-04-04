"""Template resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate._pagination import PaginatedResponse
from runcrate.models.shared import ListMeta
from runcrate.models.templates import Template


class Templates:
    """Synchronous template operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = None,
    ) -> PaginatedResponse[Template]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if search is not None:
            params["search"] = search
        if category is not None:
            params["category"] = category
        if sort_by is not None:
            params["sort_by"] = sort_by
        if sort_dir is not None:
            params["sort_dir"] = sort_dir
        data, meta = self._transport.request(
            "GET", "/api/v1/templates", params=params, cast_to=list[Template]
        )
        return PaginatedResponse(
            data=data,
            meta=ListMeta.model_validate(meta) if meta else None,
        )


class AsyncTemplates:
    """Asynchronous template operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = None,
    ) -> PaginatedResponse[Template]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if search is not None:
            params["search"] = search
        if category is not None:
            params["category"] = category
        if sort_by is not None:
            params["sort_by"] = sort_by
        if sort_dir is not None:
            params["sort_dir"] = sort_dir
        data, meta = await self._transport.request(
            "GET", "/api/v1/templates", params=params, cast_to=list[Template]
        )
        return PaginatedResponse(
            data=data,
            meta=ListMeta.model_validate(meta) if meta else None,
        )
