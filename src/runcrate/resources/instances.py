"""Instance resources."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from runcrate.models.instances import Instance, InstanceCreate, InstanceStatus, InstanceType


class _Unchanged:
    """Marks an ``update`` argument that was not passed, as opposed to ``None`` (turn off)."""

    def __repr__(self) -> str:
        return "UNCHANGED"


UNCHANGED: Any = _Unchanged()


def _auto_stop_body(max_runtime_minutes: Any, idle_shutdown_minutes: Any) -> dict[str, Any]:
    """The PATCH body: only the limits that were passed; ``None`` is sent as null."""
    body: dict[str, Any] = {}
    if max_runtime_minutes is not UNCHANGED:
        body["max_runtime_minutes"] = max_runtime_minutes
    if idle_shutdown_minutes is not UNCHANGED:
        body["idle_shutdown_minutes"] = idle_shutdown_minutes
    if not body:
        raise ValueError("Pass max_runtime_minutes, idle_shutdown_minutes or both (None turns one off).")
    return body


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
        max_runtime_minutes: Optional[int] = None,
        idle_shutdown_minutes: Optional[int] = None,
    ) -> Instance:
        """Launch a GPU instance.

        Args:
            max_runtime_minutes: Terminate the instance automatically after it has been
                running this many minutes (5 to 10080). The clock starts when the instance
                first becomes running, and an alert goes out 10 minutes before the stop.
                ``None`` (the default) means no limit.
            idle_shutdown_minutes: Terminate the instance once GPU utilisation stays under
                5% with nobody connected (SSH, web terminal or editor) for this many minutes
                (5 to 1440). GPU instances only. ``None`` (the default) turns idle stop off.

        Set both when an agent or script launches instances unattended, so a forgotten
        instance stops on its own. Values out of range raise ``BadRequestError``. A launch
        in an environment that has reached its monthly budget raises
        ``InsufficientCreditsError`` with ``code == "BUDGET_REACHED"``.
        """
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
            max_runtime_minutes=max_runtime_minutes,
            idle_shutdown_minutes=idle_shutdown_minutes,
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

    def update(
        self,
        id: str,
        *,
        max_runtime_minutes: Optional[int] = UNCHANGED,
        idle_shutdown_minutes: Optional[int] = UNCHANGED,
    ) -> Instance:
        """Change a starting or running instance's auto stop, by id or unique name.

        Args:
            max_runtime_minutes: Total minutes the instance may run, counted from when it
                started running (5 to 10080). A change never stops it sooner than 2 minutes
                from now. Extend it before a long job. ``None`` turns it off.
            idle_shutdown_minutes: Minutes of GPU utilisation under 5% with nobody connected
                before termination (5 to 1440). GPU instances launched with idle stop
                support only. ``None`` turns it off.

        Leave an argument out to keep its value. Returns the instance with its new
        ``auto_stop_at``. Raises ``ConflictError`` (409) when the instance is not live, has
        no GPU for idle stop, or was launched before idle stop existed.
        """
        data, _ = self._transport.request(
            "PATCH",
            f"/api/v1/instances/{quote(id, safe='')}",
            json=_auto_stop_body(max_runtime_minutes, idle_shutdown_minutes),
            cast_to=Instance,
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
        max_runtime_minutes: Optional[int] = None,
        idle_shutdown_minutes: Optional[int] = None,
    ) -> Instance:
        """Launch a GPU instance.

        Args:
            max_runtime_minutes: Terminate the instance automatically after it has been
                running this many minutes (5 to 10080). The clock starts when the instance
                first becomes running, and an alert goes out 10 minutes before the stop.
                ``None`` (the default) means no limit.
            idle_shutdown_minutes: Terminate the instance once GPU utilisation stays under
                5% with nobody connected (SSH, web terminal or editor) for this many minutes
                (5 to 1440). GPU instances only. ``None`` (the default) turns idle stop off.

        Set both when an agent or script launches instances unattended, so a forgotten
        instance stops on its own. Values out of range raise ``BadRequestError``. A launch
        in an environment that has reached its monthly budget raises
        ``InsufficientCreditsError`` with ``code == "BUDGET_REACHED"``.
        """
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
            max_runtime_minutes=max_runtime_minutes,
            idle_shutdown_minutes=idle_shutdown_minutes,
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

    async def update(
        self,
        id: str,
        *,
        max_runtime_minutes: Optional[int] = UNCHANGED,
        idle_shutdown_minutes: Optional[int] = UNCHANGED,
    ) -> Instance:
        """Change a starting or running instance's auto stop, by id or unique name.

        Args:
            max_runtime_minutes: Total minutes the instance may run, counted from when it
                started running (5 to 10080). A change never stops it sooner than 2 minutes
                from now. Extend it before a long job. ``None`` turns it off.
            idle_shutdown_minutes: Minutes of GPU utilisation under 5% with nobody connected
                before termination (5 to 1440). GPU instances launched with idle stop
                support only. ``None`` turns it off.

        Leave an argument out to keep its value. Returns the instance with its new
        ``auto_stop_at``. Raises ``ConflictError`` (409) when the instance is not live, has
        no GPU for idle stop, or was launched before idle stop existed.
        """
        data, _ = await self._transport.request(
            "PATCH",
            f"/api/v1/instances/{quote(id, safe='')}",
            json=_auto_stop_body(max_runtime_minutes, idle_shutdown_minutes),
            cast_to=Instance,
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
