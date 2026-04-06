"""Model inference resources — chat, images, video, TTS, transcription."""

from __future__ import annotations

import json
import time
from typing import Any, BinaryIO, Iterator, AsyncIterator, Optional, Union

import httpx

from runcrate._exceptions import make_api_error
from runcrate.models.models import (
    ChatCompletion,
    ChatCompletionRequest,
    ChatMessage,
    ImageGeneration,
    ImageGenerationRequest,
    TTSRequest,
    Transcription,
    VideoGenerationRequest,
    VideoJob,
)


class Models:
    """Synchronous model inference operations."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[Union[str, list[str]]] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Union[ChatCompletion, Iterator[dict[str, Any]]]:
        parsed_messages = [ChatMessage(**m) for m in messages]
        body = ChatCompletionRequest(
            model=model,
            messages=parsed_messages,
            stream=stream,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
        ).model_dump(exclude_none=True)

        if stream:
            return self._stream_chat(body)

        response = self._client.post("/v1/chat/completions", json=body)
        if response.status_code >= 400:
            raise make_api_error(response)
        return ChatCompletion.model_validate(response.json())

    def _stream_chat(self, body: dict[str, Any]) -> Iterator[dict[str, Any]]:
        with self._client.stream("POST", "/v1/chat/completions", json=body) as response:
            if response.status_code >= 400:
                response.read()
                raise make_api_error(response)
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    return
                yield json.loads(data)

    def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        aspect_ratio: Optional[str] = None,
        response_format: Optional[str] = None,
        num_inference_steps: Optional[int] = None,
        guidance: Optional[float] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
    ) -> ImageGeneration:
        body = ImageGenerationRequest(
            model=model,
            prompt=prompt,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            response_format=response_format,
            num_inference_steps=num_inference_steps,
            guidance=guidance,
            seed=seed,
            negative_prompt=negative_prompt,
        ).model_dump(exclude_none=True)

        response = self._client.post("/v1/images/generations", json=body, timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return ImageGeneration.model_validate(response.json())

    def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        duration: Optional[float] = None,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> VideoJob:
        body = VideoGenerationRequest(
            model=model,
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
        ).model_dump(exclude_none=True)

        response = self._client.post("/v1/videos", json=body, timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return VideoJob.model_validate(response.json())

    def get_video_status(self, id: str) -> VideoJob:
        response = self._client.get(f"/v1/videos/{id}")
        if response.status_code >= 400:
            raise make_api_error(response)
        return VideoJob.model_validate(response.json())

    def download_video(self, id: str) -> bytes:
        response = self._client.get(f"/v1/videos/{id}/download", timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return response.content

    def generate_video_and_save(
        self,
        path: str,
        *,
        model: str,
        prompt: str,
        duration: Optional[float] = None,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        poll_interval: float = 5.0,
        on_status: Optional[Any] = None,
    ) -> VideoJob:
        """Submit a video job, poll until done, and save to file.

        Args:
            path: File path to save the video (e.g. "output.mp4").
            on_status: Optional callback called with the VideoJob on each poll.
        """
        job = self.generate_video(
            model=model,
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
        )

        while job.status not in ("completed", "failed"):
            time.sleep(poll_interval)
            job = self.get_video_status(job.id)
            if on_status:
                on_status(job)

        if job.status == "failed":
            raise RuntimeError(f"Video generation failed (job {job.id})")

        video_bytes = self.download_video(job.id)
        with open(path, "wb") as f:
            f.write(video_bytes)

        return job

    def text_to_speech(
        self,
        *,
        model: str,
        input: str,
        voice: Optional[str] = None,
        response_format: Optional[str] = None,
    ) -> bytes:
        body = TTSRequest(
            model=model,
            input=input,
            voice=voice,
            response_format=response_format,
        ).model_dump(exclude_none=True)

        response = self._client.post("/v1/audio/speech", json=body, timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return response.content

    def transcribe(
        self,
        *,
        model: str,
        file: Union[bytes, BinaryIO],
        filename: str = "audio.wav",
    ) -> Transcription:
        if isinstance(file, bytes):
            files = {"file": (filename, file)}
        else:
            files = {"file": (filename, file)}

        response = self._client.post(
            "/v1/audio/transcriptions",
            data={"model": model},
            files=files,
            timeout=120.0,
        )
        if response.status_code >= 400:
            raise make_api_error(response)
        return Transcription.model_validate(response.json())


class AsyncModels:
    """Asynchronous model inference operations."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[Union[str, list[str]]] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Union[ChatCompletion, AsyncIterator[dict[str, Any]]]:
        parsed_messages = [ChatMessage(**m) for m in messages]
        body = ChatCompletionRequest(
            model=model,
            messages=parsed_messages,
            stream=stream,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
        ).model_dump(exclude_none=True)

        if stream:
            return self._stream_chat(body)

        response = await self._client.post("/v1/chat/completions", json=body)
        if response.status_code >= 400:
            raise make_api_error(response)
        return ChatCompletion.model_validate(response.json())

    async def _stream_chat(self, body: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        async with self._client.stream("POST", "/v1/chat/completions", json=body) as response:
            if response.status_code >= 400:
                await response.aread()
                raise make_api_error(response)
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    return
                yield json.loads(data)

    async def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        aspect_ratio: Optional[str] = None,
        response_format: Optional[str] = None,
        num_inference_steps: Optional[int] = None,
        guidance: Optional[float] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
    ) -> ImageGeneration:
        body = ImageGenerationRequest(
            model=model,
            prompt=prompt,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            response_format=response_format,
            num_inference_steps=num_inference_steps,
            guidance=guidance,
            seed=seed,
            negative_prompt=negative_prompt,
        ).model_dump(exclude_none=True)

        response = await self._client.post("/v1/images/generations", json=body, timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return ImageGeneration.model_validate(response.json())

    async def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        duration: Optional[float] = None,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> VideoJob:
        body = VideoGenerationRequest(
            model=model,
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
        ).model_dump(exclude_none=True)

        response = await self._client.post("/v1/videos", json=body, timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return VideoJob.model_validate(response.json())

    async def get_video_status(self, id: str) -> VideoJob:
        response = await self._client.get(f"/v1/videos/{id}")
        if response.status_code >= 400:
            raise make_api_error(response)
        return VideoJob.model_validate(response.json())

    async def download_video(self, id: str) -> bytes:
        response = await self._client.get(f"/v1/videos/{id}/download", timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return response.content

    async def generate_video_and_save(
        self,
        path: str,
        *,
        model: str,
        prompt: str,
        duration: Optional[float] = None,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        poll_interval: float = 5.0,
        on_status: Optional[Any] = None,
    ) -> VideoJob:
        """Submit a video job, poll until done, and save to file."""
        import asyncio

        job = await self.generate_video(
            model=model,
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
        )

        while job.status not in ("completed", "failed"):
            await asyncio.sleep(poll_interval)
            job = await self.get_video_status(job.id)
            if on_status:
                on_status(job)

        if job.status == "failed":
            raise RuntimeError(f"Video generation failed (job {job.id})")

        video_bytes = await self.download_video(job.id)
        with open(path, "wb") as f:
            f.write(video_bytes)

        return job

    async def text_to_speech(
        self,
        *,
        model: str,
        input: str,
        voice: Optional[str] = None,
        response_format: Optional[str] = None,
    ) -> bytes:
        body = TTSRequest(
            model=model,
            input=input,
            voice=voice,
            response_format=response_format,
        ).model_dump(exclude_none=True)

        response = await self._client.post("/v1/audio/speech", json=body, timeout=120.0)
        if response.status_code >= 400:
            raise make_api_error(response)
        return response.content

    async def transcribe(
        self,
        *,
        model: str,
        file: Union[bytes, BinaryIO],
        filename: str = "audio.wav",
    ) -> Transcription:
        if isinstance(file, bytes):
            files = {"file": (filename, file)}
        else:
            files = {"file": (filename, file)}

        response = await self._client.post(
            "/v1/audio/transcriptions",
            data={"model": model},
            files=files,
            timeout=120.0,
        )
        if response.status_code >= 400:
            raise make_api_error(response)
        return Transcription.model_validate(response.json())
