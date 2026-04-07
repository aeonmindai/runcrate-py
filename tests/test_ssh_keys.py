"""Tests for SSH keys resource."""

from __future__ import annotations

import httpx
import respx

from runcrate import Runcrate


class TestSSHKeys:
    def test_list_keys(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/ssh-keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "k1",
                            "name": "laptop",
                            "fingerprint": "SHA256:abc123",
                        },
                        {
                            "id": "k2",
                            "name": "desktop",
                            "fingerprint": "SHA256:def456",
                        },
                    ]
                },
            )
        )

        keys = client.ssh_keys.list()
        assert len(keys) == 2
        assert keys[0].id == "k1"
        assert keys[0].name == "laptop"
        assert keys[0].fingerprint == "SHA256:abc123"

    def test_create_key(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/ssh-keys").mock(
            return_value=httpx.Response(
                201,
                json={
                    "data": {
                        "id": "k-new",
                        "name": "my-key",
                        "fingerprint": "SHA256:xyz789",
                    }
                },
            )
        )

        key = client.ssh_keys.create(
            name="my-key",
            public_key="ssh-ed25519 AAAA...",
        )
        assert key.id == "k-new"
        assert key.name == "my-key"

    def test_delete_key(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.delete("/api/v1/ssh-keys/k1").mock(
            return_value=httpx.Response(204)
        )

        client.ssh_keys.delete("k1")  # should not raise
