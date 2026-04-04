"""Shared models used across resources."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ListMeta(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    cursor: Optional[str] = None
    has_more: Optional[bool] = Field(None, alias="hasMore")
    total: Optional[int] = None
