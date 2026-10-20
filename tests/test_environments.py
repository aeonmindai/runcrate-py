"""Tests for environments resource."""

from __future__ import annotations

import httpx
import respx

from runcrate import Runcrate


class TestEnvironmentBudget:
    def test_get_parses_budget_fields(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/environments/env-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "env-1",
                        "name": "agents",
                        "monthly_budget_usd": 500.0,
                        "month_to_date_usd": 123.45,
                        "budget_remaining_usd": 376.55,
                    }
                },
            )
        )

        env = client.environments.get("env-1")
        assert env.monthly_budget_usd == 500.0
        assert env.month_to_date_usd == 123.45
        assert env.budget_remaining_usd == 376.55

    def test_get_parses_uncapped_and_old_payloads(
        self, client: Runcrate, mock_api: respx.MockRouter
    ):
        mock_api.get("/api/v1/environments/env-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "env-1",
                        "name": "agents",
                        "monthly_budget_usd": None,
                        "month_to_date_usd": 12.0,
                        "budget_remaining_usd": None,
                    }
                },
            )
        )
        mock_api.get("/api/v1/environments/env-old").mock(
            return_value=httpx.Response(200, json={"data": {"id": "env-old", "name": "old"}})
        )

        uncapped = client.environments.get("env-1")
        assert uncapped.monthly_budget_usd is None
        assert uncapped.month_to_date_usd == 12.0
        assert uncapped.budget_remaining_usd is None

        old = client.environments.get("env-old")
        assert old.monthly_budget_usd is None
        assert old.month_to_date_usd is None
        assert old.budget_remaining_usd is None
