"""Instance resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.instances import Instance, InstanceCreate, InstanceStatus, InstanceType


class Instances:
    """Synchronous instance operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self, *, search: Optional[str] = None) -> list[Instance]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        data, _ = self._transport.request(
            "GET", "/api/v1/instances", params=params or None, cast_to=list[Instance]
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
    ) -> Instance:
        body = InstanceCreate(
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
            "POST", "/api/v1/instances", json=body, cast_to=Instance
        )
        return data

    def get(self, id: str) -> Instance:
        data, _ = self._transport.request(
            "GET", f"/api/v1/instances/{id}", cast_to=Instance
        )
        return data

    def terminate(self, id: str) -> None:
        self._transport.request("DELETE", f"/api/v1/instances/{id}")

    def get_status(self, id: str) -> InstanceStatus:
        data, _ = self._transport.request(
            "GET", f"/api/v1/instances/{id}/status", cast_to=InstanceStatus
        )
        return data

    def list_types(
        self,
        *,
        gpu_type: Optional[str] = None,
        region: Optional[str] = None,
        gpu_count: Optional[int] = None,
    ) -> list[InstanceType]:
        params: dict[str, Any] = {}
        if gpu_type is not None:
            params["gpu_type"] = gpu_type
        if region is not None:
            params["region"] = region
        if gpu_count is not None:
            params["gpu_count"] = gpu_count
        data, _ = self._transport.request(
            "GET", "/api/v1/instances/types", params=params or None, cast_to=list[InstanceType]
        )
        return data


class AsyncInstances:
    """Asynchronous instance operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self, *, search: Optional[str] = None) -> list[Instance]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        data, _ = await self._transport.request(
            "GET", "/api/v1/instances", params=params or None, cast_to=list[Instance]
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
    ) -> Instance:
        body = InstanceCreate(
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
            "POST", "/api/v1/instances", json=body, cast_to=Instance
        )
        return data

    async def get(self, id: str) -> Instance:
        data, _ = await self._transport.request(
            "GET", f"/api/v1/instances/{id}", cast_to=Instance
        )
        return data

    async def terminate(self, id: str) -> None:
        await self._transport.request("DELETE", f"/api/v1/instances/{id}")

    async def get_status(self, id: str) -> InstanceStatus:
        data, _ = await self._transport.request(
            "GET", f"/api/v1/instances/{id}/status", cast_to=InstanceStatus
        )
        return data

    async def list_types(
        self,
        *,
        gpu_type: Optional[str] = None,
        region: Optional[str] = None,
        gpu_count: Optional[int] = None,
    ) -> list[InstanceType]:
        params: dict[str, Any] = {}
        if gpu_type is not None:
            params["gpu_type"] = gpu_type
        if region is not None:
            params["region"] = region
        if gpu_count is not None:
            params["gpu_count"] = gpu_count
        data, _ = await self._transport.request(
            "GET", "/api/v1/instances/types", params=params or None, cast_to=list[InstanceType]
        )
        return data
