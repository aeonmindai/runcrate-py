"""Client configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


_DEFAULT_BASE_URL = "https://www.runcrate.ai"
_DEFAULT_INFERENCE_URL = "https://api.runcrate.ai"
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_RETRIES = 3


@dataclass
class ClientConfig:
    api_key: str
    base_url: str = _DEFAULT_BASE_URL
    inference_url: str = _DEFAULT_INFERENCE_URL
    timeout: float = _DEFAULT_TIMEOUT
    max_retries: int = _DEFAULT_MAX_RETRIES
    custom_headers: dict[str, str] = field(default_factory=dict)
    environment: Optional[str] = None

    @classmethod
    def from_args(
        cls,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        inference_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        environment: Optional[str] = None,
    ) -> ClientConfig:
        resolved_key = api_key or os.environ.get("RUNCRATE_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "API key is required. Pass api_key= or set the RUNCRATE_API_KEY environment variable."
            )
        if not resolved_key.startswith("rc_live_"):
            raise ValueError("Invalid API key format. Keys must start with 'rc_live_'.")

        return cls(
            api_key=resolved_key,
            base_url=(base_url or _DEFAULT_BASE_URL).rstrip("/"),
            inference_url=(inference_url or _DEFAULT_INFERENCE_URL).rstrip("/"),
            timeout=timeout if timeout is not None else _DEFAULT_TIMEOUT,
            max_retries=max_retries if max_retries is not None else _DEFAULT_MAX_RETRIES,
            environment=environment,
        )
