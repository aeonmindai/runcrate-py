"""SSH key resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate.models.ssh_keys import SSHKey, SSHKeyCreate


class SSHKeys:
    """Synchronous SSH key operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self) -> list[SSHKey]:
        data, _ = self._transport.request(
            "GET", "/api/v1/ssh-keys", cast_to=list[SSHKey]
        )
        return data

    def create(
        self,
        *,
        name: str,
        public_key: str,
        type: Optional[str] = None,
    ) -> SSHKey:
        body = SSHKeyCreate(
            name=name, public_key=public_key, type=type
        ).model_dump(exclude_none=True)
        data, _ = self._transport.request(
            "POST", "/api/v1/ssh-keys", json=body, cast_to=SSHKey
        )
        return data

    def delete(self, id: str) -> None:
        self._transport.request("DELETE", f"/api/v1/ssh-keys/{id}")


class AsyncSSHKeys:
    """Asynchronous SSH key operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self) -> list[SSHKey]:
        data, _ = await self._transport.request(
            "GET", "/api/v1/ssh-keys", cast_to=list[SSHKey]
        )
        return data

    async def create(
        self,
        *,
        name: str,
        public_key: str,
        type: Optional[str] = None,
    ) -> SSHKey:
        body = SSHKeyCreate(
            name=name, public_key=public_key, type=type
        ).model_dump(exclude_none=True)
        data, _ = await self._transport.request(
            "POST", "/api/v1/ssh-keys", json=body, cast_to=SSHKey
        )
        return data

    async def delete(self, id: str) -> None:
        await self._transport.request("DELETE", f"/api/v1/ssh-keys/{id}")
