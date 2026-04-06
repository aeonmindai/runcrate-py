"""Billing models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Balance(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    credits_balance: float = Field(alias="creditsBalance")
    active_usage_cost: float = Field(alias="activeUsageCost")


class Transaction(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    project_id: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class UsageSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_requests: Optional[int] = None
    total_prompt_tokens: Optional[int] = None
    total_completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    total_cost: Optional[float] = None
