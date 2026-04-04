"""Shared test fixtures."""

from __future__ import annotations

import httpx
import pytest
import respx

from runcrate import Runcrate


@pytest.fixture
def base_url() -> str:
    return "https://test.runcrate.com"


@pytest.fixture
def api_key() -> str:
    return "rc_live_test_key_123"


@pytest.fixture
def mock_api(base_url: str) -> respx.MockRouter:
    with respx.mock(base_url=base_url) as router:
        yield router


@pytest.fixture
def client(api_key: str, base_url: str, mock_api: respx.MockRouter) -> Runcrate:
    c = Runcrate(api_key=api_key, base_url=base_url, max_retries=0)
    yield c
    c.close()
