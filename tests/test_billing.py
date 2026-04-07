"""Tests for billing resource."""

from __future__ import annotations

import httpx
import respx

from runcrate import Runcrate, PaginatedResponse


class TestBilling:
    def test_get_balance(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/billing/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "creditsBalance": 50.0,
                        "activeUsageCost": 2.5,
                    }
                },
            )
        )

        balance = client.billing.get_balance()
        assert balance.credits_balance == 50.0
        assert balance.active_usage_cost == 2.5

    def test_list_transactions(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/billing/transactions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "t1", "type": "credit", "amount": 50.0},
                        {"id": "t2", "type": "debit", "amount": -2.5},
                    ],
                    "meta": {"hasMore": True, "total": 100},
                },
            )
        )

        result = client.billing.list_transactions(limit=2, offset=0)
        assert isinstance(result, PaginatedResponse)
        assert len(result.data) == 2
        assert result.data[0].id == "t1"
        assert result.data[0].amount == 50.0
        assert result.has_more is True
        assert result.total == 100

    def test_list_transactions_with_type_filter(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/billing/transactions").mock(
            return_value=httpx.Response(200, json={"data": [], "meta": {}})
        )

        client.billing.list_transactions(type="credit")
        assert route.calls[0].request.url.params["type"] == "credit"

    def test_usage(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.get("/api/v1/billing/usage").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "total_requests": 500,
                        "total_tokens": 100000,
                        "total_cost": 5.0,
                    }
                },
            )
        )

        usage = client.billing.usage(from_date="2025-01-01", to_date="2025-01-31")
        assert usage.total_requests == 500
        assert usage.total_cost == 5.0

    def test_usage_with_date_params(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/billing/usage").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )

        client.billing.usage(from_date="2025-01-01", to_date="2025-01-31")
        assert route.calls[0].request.url.params["from"] == "2025-01-01"
        assert route.calls[0].request.url.params["to"] == "2025-01-31"
