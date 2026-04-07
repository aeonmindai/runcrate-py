"""Tests for models resource (inference API)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from runcrate import Runcrate
from runcrate.models.models import ChatCompletion, ImageGeneration, VideoJob, Transcription


@pytest.fixture
def inference_url() -> str:
    return "https://test-api.runcrate.ai"


@pytest.fixture
def inference_client(api_key: str, base_url: str, inference_url: str) -> Runcrate:
    c = Runcrate(api_key=api_key, base_url=base_url, inference_url=inference_url)
    yield c
    c.close()


class TestChatCompletion:
    def test_chat_completion(self, inference_client: Runcrate, inference_url: str):
        completion_response = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": "deepseek-ai/DeepSeek-V3",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        mock_response = httpx.Response(200, json=completion_response)
        with patch.object(
            inference_client.models._client, "post", return_value=mock_response
        ) as mock_post:
            result = inference_client.models.chat_completion(
                model="deepseek-ai/DeepSeek-V3",
                messages=[{"role": "user", "content": "Hi"}],
            )

            assert isinstance(result, ChatCompletion)
            assert result.id == "chatcmpl-1"
            assert result.choices[0].message.content == "Hello!"
            assert result.usage.total_tokens == 15
            mock_post.assert_called_once()

    def test_chat_completion_with_params(self, inference_client: Runcrate):
        completion_response = {
            "id": "chatcmpl-2",
            "object": "chat.completion",
            "model": "test",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
            ],
        }

        mock_response = httpx.Response(200, json=completion_response)
        with patch.object(
            inference_client.models._client, "post", return_value=mock_response
        ) as mock_post:
            inference_client.models.chat_completion(
                model="test",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
                temperature=0.7,
                top_p=0.9,
                stop=["\n"],
            )

            call_kwargs = mock_post.call_args
            body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert body["max_tokens"] == 100
            assert body["temperature"] == 0.7
            assert body["top_p"] == 0.9
            assert body["stop"] == ["\n"]

    def test_chat_completion_streaming(self, inference_client: Runcrate):
        sse_lines = [
            b'data: {"id":"1","choices":[{"index":0,"delta":{"content":"Hello"}}]}\n',
            b'data: {"id":"1","choices":[{"index":0,"delta":{"content":" world"}}]}\n',
            b"data: [DONE]\n",
        ]

        mock_stream_response = MagicMock()
        mock_stream_response.status_code = 200
        mock_stream_response.iter_lines.return_value = [
            line.decode().strip() for line in sse_lines
        ]
        mock_stream_response.__enter__ = MagicMock(return_value=mock_stream_response)
        mock_stream_response.__exit__ = MagicMock(return_value=False)

        with patch.object(
            inference_client.models._client, "stream", return_value=mock_stream_response
        ):
            chunks = list(
                inference_client.models.chat_completion(
                    model="test",
                    messages=[{"role": "user", "content": "Hi"}],
                    stream=True,
                )
            )

            assert len(chunks) == 2
            assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
            assert chunks[1]["choices"][0]["delta"]["content"] == " world"


class TestImageGeneration:
    def test_generate_image(self, inference_client: Runcrate):
        image_response = {
            "created": 1234567890,
            "data": [{"url": "https://example.com/image.png", "revised_prompt": "A cat"}],
        }

        mock_response = httpx.Response(200, json=image_response)
        with patch.object(
            inference_client.models._client, "post", return_value=mock_response
        ) as mock_post:
            result = inference_client.models.generate_image(
                model="black-forest-labs/FLUX.1-schnell",
                prompt="A cat",
                width=1024,
                height=768,
            )

            assert isinstance(result, ImageGeneration)
            assert len(result.data) == 1
            assert result.data[0].url == "https://example.com/image.png"

    def test_generate_image_with_all_params(self, inference_client: Runcrate):
        mock_response = httpx.Response(200, json={"data": [{"url": "test"}]})
        with patch.object(
            inference_client.models._client, "post", return_value=mock_response
        ) as mock_post:
            inference_client.models.generate_image(
                model="test",
                prompt="test",
                aspect_ratio="16:9",
                num_inference_steps=20,
                guidance=7.5,
                seed=42,
                negative_prompt="blurry",
            )

            body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
            assert body["aspect_ratio"] == "16:9"
            assert body["seed"] == 42
            assert body["negative_prompt"] == "blurry"


class TestVideoGeneration:
    def test_generate_video(self, inference_client: Runcrate):
        job_response = {"id": "vid_1", "status": "queued"}

        mock_response = httpx.Response(200, json=job_response)
        with patch.object(
            inference_client.models._client, "post", return_value=mock_response
        ):
            result = inference_client.models.generate_video(
                model="google/veo-3.0",
                prompt="A drone over mountains",
                duration=8,
            )

            assert isinstance(result, VideoJob)
            assert result.id == "vid_1"
            assert result.status == "queued"

    def test_get_video_status(self, inference_client: Runcrate):
        mock_response = httpx.Response(200, json={"id": "vid_1", "status": "processing"})
        with patch.object(
            inference_client.models._client, "get", return_value=mock_response
        ):
            result = inference_client.models.get_video_status("vid_1")
            assert result.status == "processing"

    def test_download_video(self, inference_client: Runcrate):
        video_bytes = b"\x00\x01\x02\x03\x04"
        mock_response = httpx.Response(200, content=video_bytes)
        with patch.object(
            inference_client.models._client, "get", return_value=mock_response
        ):
            result = inference_client.models.download_video("vid_1")
            assert result == video_bytes


class TestTextToSpeech:
    def test_text_to_speech(self, inference_client: Runcrate):
        audio_bytes = b"\xff\xfb\x90\x00" * 100  # fake mp3 data
        mock_response = httpx.Response(200, content=audio_bytes)
        with patch.object(
            inference_client.models._client, "post", return_value=mock_response
        ):
            result = inference_client.models.text_to_speech(
                model="hexgrad/Kokoro-82M",
                input="Hello from Runcrate!",
                voice="af_heart",
            )

            assert isinstance(result, bytes)
            assert len(result) == len(audio_bytes)


class TestTranscription:
    def test_transcribe(self, inference_client: Runcrate):
        transcription_response = {
            "text": "Hello world",
            "duration": 2.5,
            "language": "en",
        }

        mock_response = httpx.Response(200, json=transcription_response)
        with patch.object(
            inference_client.models._client, "post", return_value=mock_response
        ):
            result = inference_client.models.transcribe(
                model="openai/whisper-1",
                file=b"\x00\x01\x02",
                filename="test.wav",
            )

            assert isinstance(result, Transcription)
            assert result.text == "Hello world"
            assert result.duration == 2.5
            assert result.language == "en"
