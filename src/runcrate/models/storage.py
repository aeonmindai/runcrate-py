"""Storage models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StorageVolume(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    name: str
    size_gb: Optional[int] = Field(None, alias="sizeGb")
    status: Optional[str] = None
    region: Optional[str] = None
    provider_type: Optional[str] = Field(None, alias="providerType")
    deployment_id: Optional[str] = Field(None, alias="deploymentId")
    project_id: Optional[str] = Field(None, alias="projectId")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class StorageCreate(BaseModel):
    name: str
    size_gb: int
    region: str


class StorageDeleteResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str
    refund_amount: Optional[float] = None


class StorageRegion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    provider: str
