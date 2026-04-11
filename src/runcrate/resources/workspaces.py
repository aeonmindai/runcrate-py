"""Workspace resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.workspaces import Workspace, WorkspaceCreate, WorkspaceUpdate


class Workspaces:
    """Synchronous workspace operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self) -> list[Workspace]:
        data, _ = self._transport.request(
            "GET", "/api/v1/workspaces", cast_to=list[Workspace]
        )
        return data

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Workspace:
        body = WorkspaceCreate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "POST", "/api/v1/workspaces", json=body, cast_to=Workspace
        )
        return data

    def get(self, id: str) -> Workspace:
        data, _ = self._transport.request(
            "GET", f"/api/v1/workspaces/{id}", cast_to=Workspace
        )
        return data

    def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Workspace:
        body = WorkspaceUpdate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "PATCH", f"/api/v1/workspaces/{id}", json=body, cast_to=Workspace
        )
        return data

    def delete(self, id: str) -> None:
        self._transport.request("DELETE", f"/api/v1/workspaces/{id}")


class AsyncWorkspaces:
    """Asynchronous workspace operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self) -> list[Workspace]:
        data, _ = await self._transport.request(
            "GET", "/api/v1/workspaces", cast_to=list[Workspace]
        )
        return data

    async def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Workspace:
        body = WorkspaceCreate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "POST", "/api/v1/workspaces", json=body, cast_to=Workspace
        )
        return data

    async def get(self, id: str) -> Workspace:
        data, _ = await self._transport.request(
            "GET", f"/api/v1/workspaces/{id}", cast_to=Workspace
        )
        return data

    async def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Workspace:
        body = WorkspaceUpdate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "PATCH", f"/api/v1/workspaces/{id}", json=body, cast_to=Workspace
        )
        return data

    async def delete(self, id: str) -> None:
        await self._transport.request("DELETE", f"/api/v1/workspaces/{id}")
