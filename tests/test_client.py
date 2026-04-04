"""Tests for client initialization and configuration."""

from __future__ import annotations

import os

import pytest

from runcrate import Runcrate, AsyncRuncrate


class TestClientInit:
    def test_valid_api_key(self):
        client = Runcrate(api_key="rc_live_test123")
        assert client._config.api_key == "rc_live_test123"
        client.close()

    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="API key is required"):
            Runcrate(api_key=None)

    def test_invalid_api_key_prefix(self):
        with pytest.raises(ValueError, match="must start with 'rc_live_'"):
            Runcrate(api_key="sk_invalid_key")

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("RUNCRATE_API_KEY", "rc_live_from_env")
        client = Runcrate()
        assert client._config.api_key == "rc_live_from_env"
        client.close()

    def test_custom_base_url(self):
        client = Runcrate(api_key="rc_live_test", base_url="https://staging.runcrate.com")
        assert client._config.base_url == "https://staging.runcrate.com"
        client.close()

    def test_trailing_slash_stripped(self):
        client = Runcrate(api_key="rc_live_test", base_url="https://runcrate.com/")
        assert client._config.base_url == "https://runcrate.com"
        client.close()

    def test_custom_timeout(self):
        client = Runcrate(api_key="rc_live_test", timeout=60.0)
        assert client._config.timeout == 60.0
        client.close()

    def test_custom_max_retries(self):
        client = Runcrate(api_key="rc_live_test", max_retries=5)
        assert client._config.max_retries == 5
        client.close()

    def test_context_manager(self):
        with Runcrate(api_key="rc_live_test") as client:
            assert client.instances is not None

    def test_resource_namespaces_exist(self):
        client = Runcrate(api_key="rc_live_test")
        assert hasattr(client, "instances")
        assert hasattr(client, "crates")
        assert hasattr(client, "projects")
        assert hasattr(client, "ssh_keys")
        assert hasattr(client, "storage")
        assert hasattr(client, "billing")
        assert hasattr(client, "templates")
        client.close()


class TestAsyncClientInit:
    def test_valid_api_key(self):
        client = AsyncRuncrate(api_key="rc_live_test123")
        assert client._config.api_key == "rc_live_test123"

    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="API key is required"):
            AsyncRuncrate(api_key=None)
