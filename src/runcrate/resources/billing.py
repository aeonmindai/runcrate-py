"""Billing resources."""

from __future__ import annotations

from typing import Any, Optional

from runcrate._pagination import PaginatedResponse
from runcrate.models.billing import Balance, Transaction, UsageSummary
from runcrate.models.shared import ListMeta


class Billing:
    """Synchronous billing operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def get_balance(self) -> Balance:
        data, _ = self._transport.request(
            "GET", "/api/v1/billing/balance", cast_to=Balance
        )
        return data

    def list_transactions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        type: Optional[str] = None,
    ) -> PaginatedResponse[Transaction]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if type is not None:
            params["type"] = type
        data, meta = self._transport.request(
            "GET", "/api/v1/billing/transactions", params=params, cast_to=list[Transaction]
        )
        return PaginatedResponse(
            data=data,
            meta=ListMeta.model_validate(meta) if meta else None,
        )

    def usage(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> UsageSummary:
        params: dict[str, Any] = {}
        if from_date is not None:
            params["from"] = from_date
        if to_date is not None:
            params["to"] = to_date
        data, _ = self._transport.request(
            "GET", "/api/v1/billing/usage", params=params or None, cast_to=UsageSummary
        )
        return data


class AsyncBilling:
    """Asynchronous billing operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def get_balance(self) -> Balance:
        data, _ = await self._transport.request(
            "GET", "/api/v1/billing/balance", cast_to=Balance
        )
        return data

    async def list_transactions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        type: Optional[str] = None,
    ) -> PaginatedResponse[Transaction]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if type is not None:
            params["type"] = type
        data, meta = await self._transport.request(
            "GET", "/api/v1/billing/transactions", params=params, cast_to=list[Transaction]
        )
        return PaginatedResponse(
            data=data,
            meta=ListMeta.model_validate(meta) if meta else None,
        )

    async def usage(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> UsageSummary:
        params: dict[str, Any] = {}
        if from_date is not None:
            params["from"] = from_date
        if to_date is not None:
            params["to"] = to_date
        data, _ = await self._transport.request(
            "GET", "/api/v1/billing/usage", params=params or None, cast_to=UsageSummary
        )
        return data
