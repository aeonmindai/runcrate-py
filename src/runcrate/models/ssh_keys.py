"""SSH key models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SSHKey(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    name: str
    fingerprint: Optional[str] = None
    type: Optional[str] = None
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    last_used: Optional[datetime] = Field(None, alias="lastUsed")
    project_id: Optional[str] = Field(None, alias="projectId")


class SSHKeyCreate(BaseModel):
    name: str
    public_key: str
    type: Optional[str] = None
