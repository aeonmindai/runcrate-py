"""Crate resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.crates import Crate, CrateCreate


class Crates:
    """Synchronous crate operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self, *, search: Optional[str] = None) -> list[Crate]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        data, _ = self._transport.request(
            "GET", "/api/v1/crates", params=params or None, cast_to=list[Crate]
        )
        return data

    def create(
        self,
        *,
        name: str,
        ssh_key_id: str,
        gpu_type: Optional[str] = None,
        instance_type_id: Optional[str] = None,
        region: Optional[str] = None,
        gpu_count: Optional[int] = None,
        cpu_cores: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        template: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
        startup_commands: Optional[list[str]] = None,
        storage_id: Optional[str] = None,
        launch_script: Optional[str] = None,
        launch_script_base64: Optional[str] = None,
    ) -> Crate:
        body = CrateCreate(
            name=name,
            ssh_key_id=ssh_key_id,
            gpu_type=gpu_type,
            instance_type_id=instance_type_id,
            region=region,
            gpu_count=gpu_count,
            cpu_cores=cpu_cores,
            memory=memory,
            storage=storage,
            template=template,
            env_vars=env_vars,
            startup_commands=startup_commands,
            storage_id=storage_id,
            launch_script=launch_script,
            launch_script_base64=launch_script_base64,
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "POST", "/api/v1/crates", json=body, cast_to=Crate
        )
        return data

    def get(self, id: str) -> Crate:
        data, _ = self._transport.request(
            "GET", f"/api/v1/crates/{id}", cast_to=Crate
        )
        return data

    def terminate(self, id: str) -> None:
        self._transport.request("DELETE", f"/api/v1/crates/{id}")


class AsyncCrates:
    """Asynchronous crate operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self, *, search: Optional[str] = None) -> list[Crate]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        data, _ = await self._transport.request(
            "GET", "/api/v1/crates", params=params or None, cast_to=list[Crate]
        )
        return data

    async def create(
        self,
        *,
        name: str,
        ssh_key_id: str,
        gpu_type: Optional[str] = None,
        instance_type_id: Optional[str] = None,
        region: Optional[str] = None,
        gpu_count: Optional[int] = None,
        cpu_cores: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        template: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
        startup_commands: Optional[list[str]] = None,
        storage_id: Optional[str] = None,
        launch_script: Optional[str] = None,
        launch_script_base64: Optional[str] = None,
    ) -> Crate:
        body = CrateCreate(
            name=name,
            ssh_key_id=ssh_key_id,
            gpu_type=gpu_type,
            instance_type_id=instance_type_id,
            region=region,
            gpu_count=gpu_count,
            cpu_cores=cpu_cores,
            memory=memory,
            storage=storage,
            template=template,
            env_vars=env_vars,
            startup_commands=startup_commands,
            storage_id=storage_id,
            launch_script=launch_script,
            launch_script_base64=launch_script_base64,
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "POST", "/api/v1/crates", json=body, cast_to=Crate
        )
        return data

    async def get(self, id: str) -> Crate:
        data, _ = await self._transport.request(
            "GET", f"/api/v1/crates/{id}", cast_to=Crate
        )
        return data

    async def terminate(self, id: str) -> None:
        await self._transport.request("DELETE", f"/api/v1/crates/{id}")
