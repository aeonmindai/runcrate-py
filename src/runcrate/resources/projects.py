"""Project resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.projects import Project, ProjectCreate, ProjectUpdate


class Projects:
    """Synchronous project operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self) -> list[Project]:
        data, _ = self._transport.request(
            "GET", "/api/v1/projects", cast_to=list[Project]
        )
        return data

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Project:
        body = ProjectCreate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "POST", "/api/v1/projects", json=body, cast_to=Project
        )
        return data

    def get(self, id: str) -> Project:
        data, _ = self._transport.request(
            "GET", f"/api/v1/projects/{id}", cast_to=Project
        )
        return data

    def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Project:
        body = ProjectUpdate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "PATCH", f"/api/v1/projects/{id}", json=body, cast_to=Project
        )
        return data

    def delete(self, id: str) -> None:
        self._transport.request("DELETE", f"/api/v1/projects/{id}")


class AsyncProjects:
    """Asynchronous project operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self) -> list[Project]:
        data, _ = await self._transport.request(
            "GET", "/api/v1/projects", cast_to=list[Project]
        )
        return data

    async def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Project:
        body = ProjectCreate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "POST", "/api/v1/projects", json=body, cast_to=Project
        )
        return data

    async def get(self, id: str) -> Project:
        data, _ = await self._transport.request(
            "GET", f"/api/v1/projects/{id}", cast_to=Project
        )
        return data

    async def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Project:
        body = ProjectUpdate(
            name=name, description=description, is_default=is_default
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "PATCH", f"/api/v1/projects/{id}", json=body, cast_to=Project
        )
        return data

    async def delete(self, id: str) -> None:
        await self._transport.request("DELETE", f"/api/v1/projects/{id}")
