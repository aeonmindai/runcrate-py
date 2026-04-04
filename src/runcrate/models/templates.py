"""Template models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Template(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    created_at: Optional[datetime] = None
