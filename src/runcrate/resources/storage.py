"""Storage resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.storage import StorageVolume


class Storage:
    """Synchronous storage operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self, *, search: Optional[str] = None) -> list[StorageVolume]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        data, _ = self._transport.request(
            "GET", "/api/v1/storage", params=params or None, cast_to=list[StorageVolume]
        )
        return data

    def get(self, id: str) -> StorageVolume:
        data, _ = self._transport.request(
            "GET", f"/api/v1/storage/{id}", cast_to=StorageVolume
        )
        return data


class AsyncStorage:
    """Asynchronous storage operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self, *, search: Optional[str] = None) -> list[StorageVolume]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        data, _ = await self._transport.request(
            "GET", "/api/v1/storage", params=params or None, cast_to=list[StorageVolume]
        )
        return data

    async def get(self, id: str) -> StorageVolume:
        data, _ = await self._transport.request(
            "GET", f"/api/v1/storage/{id}", cast_to=StorageVolume
        )
        return data
