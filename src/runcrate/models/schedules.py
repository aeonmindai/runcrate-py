"""Schedule models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict

from runcrate.models.instances import Instance

ScheduleKind = Literal["instance", "job"]
ScheduleOverlap = Literal["skip", "allow"]
ScheduleRunStatus = Literal["launched", "failed", "skipped_budget", "skipped_overlap", "no_access"]


class Schedule(BaseModel):
    """A launch that starts later: once at ``run_at``, or on a recurring ``cron``."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    kind: ScheduleKind
    environment_id: Optional[str] = None
    created_by: Optional[str] = None
    spec: dict[str, Any]
    max_runtime_minutes: Optional[int] = None
    run_at: Optional[datetime] = None
    cron: Optional[str] = None
    timezone: str = "UTC"
    overlap: ScheduleOverlap = "skip"
    enabled: bool = True
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[ScheduleRunStatus] = None
    last_error: Optional[str] = None
    last_instance_id: Optional[str] = None
    last_job_id: Optional[str] = None
    run_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScheduleRun(BaseModel):
    """What ``run_now`` launched: the updated schedule plus the new instance or job."""

    model_config = ConfigDict(extra="allow")

    schedule: Schedule
    instance: Optional[Instance] = None
    job: Optional[dict[str, Any]] = None


class ScheduleCreate(BaseModel):
    kind: ScheduleKind
    spec: dict[str, Any]
    run_at: Optional[str] = None
    cron: Optional[str] = None
    timezone: Optional[str] = None
    overlap: Optional[ScheduleOverlap] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    run_at: Optional[str] = None
    cron: Optional[str] = None
    timezone: Optional[str] = None
    overlap: Optional[ScheduleOverlap] = None
    name: Optional[str] = None
    spec: Optional[dict[str, Any]] = None
