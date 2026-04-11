"""Main client classes."""

from __future__ import annotations

from typing import Optional

import httpx

from runcrate._config import ClientConfig
from runcrate._transport import AsyncTransport, SyncTransport
from runcrate.resources.billing import AsyncBilling, Billing
from runcrate.resources.crates import AsyncCrates, Crates
from runcrate.resources.environments import AsyncEnvironments, Environments
from runcrate.resources.instances import AsyncInstances, Instances
from runcrate.resources.models import AsyncModels, Models
from runcrate.resources.projects import AsyncProjects, Projects
from runcrate.resources.ssh_keys import AsyncSSHKeys, SSHKeys
from runcrate.resources.storage import AsyncStorage, Storage
from runcrate.resources.templates import AsyncTemplates, Templates
from runcrate.resources.workspaces import AsyncWorkspaces, Workspaces


def _make_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "runcrate-python/0.1.0",
    }


class Runcrate:
    """Synchronous Runcrate API client.

    Usage::

        from runcrate import Runcrate

        client = Runcrate(api_key="rc_live_...")
        instances = client.instances.list()
        client.close()

    Or as a context manager::

        with Runcrate(api_key="rc_live_...") as client:
            instances = client.instances.list()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        inference_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._config = ClientConfig.from_args(
            api_key=api_key,
            base_url=base_url,
            inference_url=inference_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._transport = SyncTransport(self._config)

        # Separate httpx client for inference API (api.runcrate.ai)
        self._inference_client = httpx.Client(
            base_url=self._config.inference_url,
            headers=_make_headers(self._config.api_key),
            timeout=self._config.timeout,
        )

        self.instances = Instances(self._transport)
        self.crates = Crates(self._transport)
        self.workspaces = Workspaces(self._transport)
        self.environments = Environments(self._transport)
        self.projects = Projects(self._transport)  # deprecated — use workspaces
        self.ssh_keys = SSHKeys(self._transport)
        self.storage = Storage(self._transport)
        self.billing = Billing(self._transport)
        self.templates = Templates(self._transport)
        self.models = Models(self._inference_client)

    def close(self) -> None:
        self._transport.close()
        self._inference_client.close()

    def __enter__(self) -> Runcrate:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncRuncrate:
    """Asynchronous Runcrate API client.

    Usage::

        from runcrate import AsyncRuncrate

        async with AsyncRuncrate(api_key="rc_live_...") as client:
            instances = await client.instances.list()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        inference_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._config = ClientConfig.from_args(
            api_key=api_key,
            base_url=base_url,
            inference_url=inference_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._transport = AsyncTransport(self._config)

        # Separate httpx client for inference API (api.runcrate.ai)
        self._inference_client = httpx.AsyncClient(
            base_url=self._config.inference_url,
            headers=_make_headers(self._config.api_key),
            timeout=self._config.timeout,
        )

        self.instances = AsyncInstances(self._transport)
        self.crates = AsyncCrates(self._transport)
        self.workspaces = AsyncWorkspaces(self._transport)
        self.environments = AsyncEnvironments(self._transport)
        self.projects = AsyncProjects(self._transport)  # deprecated — use workspaces
        self.ssh_keys = AsyncSSHKeys(self._transport)
        self.storage = AsyncStorage(self._transport)
        self.billing = AsyncBilling(self._transport)
        self.templates = AsyncTemplates(self._transport)
        self.models = AsyncModels(self._inference_client)

    async def close(self) -> None:
        await self._transport.close()
        await self._inference_client.aclose()

    async def __aenter__(self) -> AsyncRuncrate:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
