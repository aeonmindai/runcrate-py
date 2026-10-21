"""Secret resources: the names of the environment's secrets. Values are set in the dashboard."""

from __future__ import annotations

from typing import Any

from runcrate.models.secrets import Secret


class Secrets:
    """Synchronous secret operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self) -> list[Secret]:
        """The secrets set in the client's environment, sorted by name. Never their values."""
        data, _ = self._transport.request("GET", "/api/v1/secrets", cast_to=list[Secret])
        return data


class AsyncSecrets:
    """Asynchronous secret operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self) -> list[Secret]:
        """The secrets set in the client's environment, sorted by name. Never their values."""
        data, _ = await self._transport.request("GET", "/api/v1/secrets", cast_to=list[Secret])
        return data
