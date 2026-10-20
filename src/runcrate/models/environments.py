"""Environment models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Environment(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    is_default: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    monthly_budget_usd: Optional[float] = None
    month_to_date_usd: Optional[float] = None
    budget_remaining_usd: Optional[float] = None


class EnvironmentCreate(BaseModel):
    name: str


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None
