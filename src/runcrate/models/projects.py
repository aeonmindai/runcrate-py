"""Project models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Project(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: Optional[str] = None
    is_default: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user_id: Optional[str] = None
    resource_count: Optional[int] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: Optional[bool] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
