"""Environment resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.environments import Environment, EnvironmentCreate, EnvironmentUpdate


class Environments:
    """Synchronous environment operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self) -> list[Environment]:
        data, _ = self._transport.request(
            "GET", "/api/v1/environments", cast_to=list[Environment]
        )
        return data

    def create(self, *, name: str) -> Environment:
        body = EnvironmentCreate(name=name).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "POST", "/api/v1/environments", json=body, cast_to=Environment
        )
        return data

    def get(self, id: str) -> Environment:
        data, _ = self._transport.request(
            "GET", f"/api/v1/environments/{id}", cast_to=Environment
        )
        return data

    def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Environment:
        body = EnvironmentUpdate(
            name=name, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "PATCH", f"/api/v1/environments/{id}", json=body, cast_to=Environment
        )
        return data

    def delete(self, id: str) -> None:
        self._transport.request("DELETE", f"/api/v1/environments/{id}")


class AsyncEnvironments:
    """Asynchronous environment operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self) -> list[Environment]:
        data, _ = await self._transport.request(
            "GET", "/api/v1/environments", cast_to=list[Environment]
        )
        return data

    async def create(self, *, name: str) -> Environment:
        body = EnvironmentCreate(name=name).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "POST", "/api/v1/environments", json=body, cast_to=Environment
        )
        return data

    async def get(self, id: str) -> Environment:
        data, _ = await self._transport.request(
            "GET", f"/api/v1/environments/{id}", cast_to=Environment
        )
        return data

    async def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Environment:
        body = EnvironmentUpdate(
            name=name, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "PATCH", f"/api/v1/environments/{id}", json=body, cast_to=Environment
        )
        return data

    async def delete(self, id: str) -> None:
        await self._transport.request("DELETE", f"/api/v1/environments/{id}")
