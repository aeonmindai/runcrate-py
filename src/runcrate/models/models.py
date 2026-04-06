"""Model inference types — chat completions, images, video, TTS, transcription."""

from __future__ import annotations

from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ─── Chat Completions ────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Any]]
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


class ChatChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    object: str = "chat.completion"
    created: Optional[int] = None
    model: str
    choices: List[ChatChoice]
    usage: Optional[ChatUsage] = None


# ─── Image Generation ────────────────────────────────────────────────────────


class ImageGenerationRequest(BaseModel):
    model: str
    prompt: str
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[str] = None
    response_format: Optional[str] = None
    num_inference_steps: Optional[int] = None
    guidance: Optional[float] = None
    seed: Optional[int] = None
    negative_prompt: Optional[str] = None


class ImageData(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None

    def to_bytes(self) -> bytes:
        """Get raw image bytes, handling base64 and data URIs automatically."""
        import base64 as b64

        if self.b64_json:
            return b64.b64decode(self.b64_json)
        if self.url and self.url.startswith("data:"):
            raw = self.url.split(",", 1)[1]
            return b64.b64decode(raw)
        if self.url:
            import httpx
            return httpx.get(self.url).content
        raise ValueError("No image data available")

    def save(self, path: str) -> None:
        """Save image to a file."""
        with open(path, "wb") as f:
            f.write(self.to_bytes())


class ImageGeneration(BaseModel):
    model_config = ConfigDict(extra="allow")

    created: Optional[int] = None
    data: List[ImageData]


# ─── Video Generation ────────────────────────────────────────────────────────


class VideoGenerationRequest(BaseModel):
    model: str
    prompt: str
    duration: Optional[float] = None
    aspect_ratio: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class VideoJob(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    status: str  # queued, processing, completed, failed


# ─── Text-to-Speech ──────────────────────────────────────────────────────────


class TTSRequest(BaseModel):
    model: str
    input: str
    voice: Optional[str] = None
    response_format: Optional[str] = None  # mp3 or pcm


# ─── Transcription (Speech-to-Text) ──────────────────────────────────────────


class Transcription(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    duration: Optional[float] = None
    language: Optional[str] = None
    segments: Optional[List[Any]] = None
