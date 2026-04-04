"""Instance models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class Instance(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    status: str
    gpu_type: Optional[str] = None
    gpu_count: Optional[int] = None
    cpu_cores: Optional[int] = None
    memory: Optional[int] = None
    storage: Optional[int] = None
    region: Optional[str] = None
    ip: Optional[str] = None
    os_image: Optional[str] = None
    cost_per_hour: Optional[float] = None
    deployed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InstanceCreate(BaseModel):
    name: str
    ssh_key_id: str
    gpu_type: Optional[str] = None
    instance_type_id: Optional[str] = None
    region: Optional[str] = None
    gpu_count: Optional[int] = None
    cpu_cores: Optional[int] = None
    memory: Optional[int] = None
    storage: Optional[int] = None
    template: Optional[str] = None
    env_vars: Optional[dict[str, str]] = None
    startup_commands: Optional[list[str]] = None
    storage_id: Optional[str] = None
    launch_script: Optional[str] = None
    launch_script_base64: Optional[str] = None


class InstanceStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    status: str
    ip: Optional[str] = None


class InstanceType(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    gpu_type: str
    gpu_count: int
    cpu_cores: int
    memory_gb: float
    storage_gb: float
    region: str
    deployment_type: Optional[str] = None
    hourly_rate: float
