"""Main client classes."""

from __future__ import annotations

from typing import Any, Iterator, AsyncIterator, Optional, Union

import httpx

from runcrate._config import ClientConfig
from runcrate._transport import AsyncTransport, SyncTransport
from runcrate.resources.billing import AsyncBilling, Billing
from runcrate.resources.environments import AsyncEnvironments, Environments
from runcrate.resources.instances import AsyncInstances, Instances
from runcrate.resources.models import AsyncModels, Models
from runcrate.resources.ssh_keys import AsyncSSHKeys, SSHKeys
from runcrate.resources.storage import AsyncStorage, Storage
from runcrate.resources.templates import AsyncTemplates, Templates
from runcrate.models.models import ChatCompletion, ImageGeneration, Transcription, VideoJob


# ─── OpenAI-compatible namespace classes (sync) ────────────────────────────────

class _ChatCompletions:
    """OpenAI-compatible chat.completions namespace."""

    def __init__(self, models: Models) -> None:
        self._models = models

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[ChatCompletion, Iterator[dict[str, Any]]]:
        return self._models.chat_completion(model=model, messages=messages, stream=stream, **kwargs)


class _Chat:
    """OpenAI-compatible chat namespace."""

    def __init__(self, models: Models) -> None:
        self.completions = _ChatCompletions(models)


class _Images:
    """OpenAI-compatible images namespace."""

    def __init__(self, models: Models) -> None:
        self._models = models

    def generate(self, *, model: str, prompt: str, **kwargs: Any) -> ImageGeneration:
        return self._models.generate_image(model=model, prompt=prompt, **kwargs)


class _Speech:
    """OpenAI-compatible audio.speech namespace."""

    def __init__(self, models: Models) -> None:
        self._models = models

    def create(self, *, model: str, input: str, **kwargs: Any) -> bytes:
        return self._models.text_to_speech(model=model, input=input, **kwargs)


class _Transcriptions:
    """OpenAI-compatible audio.transcriptions namespace."""

    def __init__(self, models: Models) -> None:
        self._models = models

    def create(self, *, model: str, file: Any, **kwargs: Any) -> Transcription:
        return self._models.transcribe(model=model, file=file, **kwargs)


class _Audio:
    """OpenAI-compatible audio namespace."""

    def __init__(self, models: Models) -> None:
        self.speech = _Speech(models)
        self.transcriptions = _Transcriptions(models)


class _Videos:
    """Video namespace."""

    def __init__(self, models: Models) -> None:
        self._models = models

    def generate(self, *, model: str, prompt: str, **kwargs: Any) -> VideoJob:
        return self._models.generate_video(model=model, prompt=prompt, **kwargs)

    def get_status(self, id: str) -> VideoJob:
        return self._models.get_video_status(id)

    def download(self, id: str) -> bytes:
        return self._models.download_video(id)

    def generate_and_save(self, path: str, *, model: str, prompt: str, **kwargs: Any) -> VideoJob:
        return self._models.generate_video_and_save(path, model=model, prompt=prompt, **kwargs)


# ─── OpenAI-compatible namespace classes (async) ───────────────────────────────

class _AsyncChatCompletions:
    """OpenAI-compatible chat.completions namespace (async)."""

    def __init__(self, models: AsyncModels) -> None:
        self._models = models

    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[ChatCompletion, AsyncIterator[dict[str, Any]]]:
        return await self._models.chat_completion(model=model, messages=messages, stream=stream, **kwargs)


class _AsyncChat:
    """OpenAI-compatible chat namespace (async)."""

    def __init__(self, models: AsyncModels) -> None:
        self.completions = _AsyncChatCompletions(models)


class _AsyncImages:
    """OpenAI-compatible images namespace (async)."""

    def __init__(self, models: AsyncModels) -> None:
        self._models = models

    async def generate(self, *, model: str, prompt: str, **kwargs: Any) -> ImageGeneration:
        return await self._models.generate_image(model=model, prompt=prompt, **kwargs)


class _AsyncSpeech:
    """OpenAI-compatible audio.speech namespace (async)."""

    def __init__(self, models: AsyncModels) -> None:
        self._models = models

    async def create(self, *, model: str, input: str, **kwargs: Any) -> bytes:
        return await self._models.text_to_speech(model=model, input=input, **kwargs)


class _AsyncTranscriptions:
    """OpenAI-compatible audio.transcriptions namespace (async)."""

    def __init__(self, models: AsyncModels) -> None:
        self._models = models

    async def create(self, *, model: str, file: Any, **kwargs: Any) -> Transcription:
        return await self._models.transcribe(model=model, file=file, **kwargs)


class _AsyncAudio:
    """OpenAI-compatible audio namespace (async)."""

    def __init__(self, models: AsyncModels) -> None:
        self.speech = _AsyncSpeech(models)
        self.transcriptions = _AsyncTranscriptions(models)


class _AsyncVideos:
    """Video namespace (async)."""

    def __init__(self, models: AsyncModels) -> None:
        self._models = models

    async def generate(self, *, model: str, prompt: str, **kwargs: Any) -> VideoJob:
        return await self._models.generate_video(model=model, prompt=prompt, **kwargs)

    async def get_status(self, id: str) -> VideoJob:
        return await self._models.get_video_status(id)

    async def download(self, id: str) -> bytes:
        return await self._models.download_video(id)

    async def generate_and_save(self, path: str, *, model: str, prompt: str, **kwargs: Any) -> VideoJob:
        return await self._models.generate_video_and_save(path, model=model, prompt=prompt, **kwargs)


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
        environment: Optional[str] = None,
    ) -> None:
        self._config = ClientConfig.from_args(
            api_key=api_key,
            base_url=base_url,
            inference_url=inference_url,
            timeout=timeout,
            max_retries=max_retries,
            environment=environment,
        )
        self._transport = SyncTransport(self._config)

        # Separate httpx client for inference API (api.runcrate.ai)
        self._inference_client = httpx.Client(
            base_url=self._config.inference_url,
            headers=_make_headers(self._config.api_key),
            timeout=self._config.timeout,
        )

        self.instances = Instances(self._transport)
        self.environments = Environments(self._transport)
        self.ssh_keys = SSHKeys(self._transport)
        self.storage = Storage(self._transport)
        self.billing = Billing(self._transport)
        self.templates = Templates(self._transport)
        self.models = Models(self._inference_client)

        # OpenAI-compatible aliases
        self.chat = _Chat(self.models)
        self.images = _Images(self.models)
        self.audio = _Audio(self.models)
        self.videos = _Videos(self.models)

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
        environment: Optional[str] = None,
    ) -> None:
        self._config = ClientConfig.from_args(
            api_key=api_key,
            base_url=base_url,
            inference_url=inference_url,
            timeout=timeout,
            max_retries=max_retries,
            environment=environment,
        )
        self._transport = AsyncTransport(self._config)

        # Separate httpx client for inference API (api.runcrate.ai)
        self._inference_client = httpx.AsyncClient(
            base_url=self._config.inference_url,
            headers=_make_headers(self._config.api_key),
            timeout=self._config.timeout,
        )

        self.instances = AsyncInstances(self._transport)
        self.environments = AsyncEnvironments(self._transport)
        self.ssh_keys = AsyncSSHKeys(self._transport)
        self.storage = AsyncStorage(self._transport)
        self.billing = AsyncBilling(self._transport)
        self.templates = AsyncTemplates(self._transport)
        self.models = AsyncModels(self._inference_client)

        # OpenAI-compatible aliases
        self.chat = _AsyncChat(self.models)
        self.images = _AsyncImages(self.models)
        self.audio = _AsyncAudio(self.models)
        self.videos = _AsyncVideos(self.models)

    async def close(self) -> None:
        await self._transport.close()
        await self._inference_client.aclose()

    async def __aenter__(self) -> AsyncRuncrate:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
