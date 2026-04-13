"""Storage resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.storage import StorageVolume, StorageCreate, StorageDeleteResult, StorageRegion


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

    def list_regions(self) -> list[StorageRegion]:
        data, _ = self._transport.request(
            "GET", "/api/v1/storage/regions", cast_to=list[StorageRegion]
        )
        return data

    def create(
        self,
        *,
        name: str,
        size_gb: int,
        region: str,
    ) -> StorageVolume:
        body = StorageCreate(
            name=name,
            size_gb=size_gb,
            region=region,
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "POST", "/api/v1/storage", json=body, cast_to=StorageVolume
        )
        return data

    def resize(self, id: str, *, size_gb: int) -> StorageVolume:
        data, _ = self._transport.request(
            "PATCH", f"/api/v1/storage/{id}", json={"size_gb": size_gb}, cast_to=StorageVolume
        )
        return data

    def delete(self, id: str) -> StorageDeleteResult:
        data, _ = self._transport.request(
            "DELETE", f"/api/v1/storage/{id}", cast_to=StorageDeleteResult
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

    async def list_regions(self) -> list[StorageRegion]:
        data, _ = await self._transport.request(
            "GET", "/api/v1/storage/regions", cast_to=list[StorageRegion]
        )
        return data

    async def create(
        self,
        *,
        name: str,
        size_gb: int,
        region: str,
    ) -> StorageVolume:
        body = StorageCreate(
            name=name,
            size_gb=size_gb,
            region=region,
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "POST", "/api/v1/storage", json=body, cast_to=StorageVolume
        )
        return data

    async def resize(self, id: str, *, size_gb: int) -> StorageVolume:
        data, _ = await self._transport.request(
            "PATCH", f"/api/v1/storage/{id}", json={"size_gb": size_gb}, cast_to=StorageVolume
        )
        return data

    async def delete(self, id: str) -> StorageDeleteResult:
        data, _ = await self._transport.request(
            "DELETE", f"/api/v1/storage/{id}", cast_to=StorageDeleteResult
        )
        return data
