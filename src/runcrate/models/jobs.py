"""Job models: commands run on their own fresh GPU machine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "starting", "running", "succeeded", "failed", "cancelled", "timed_out"]
"""``queued``, ``starting`` and ``running`` are live; the rest are final."""
JobRetryOn = Literal["machine_failure", "nonzero_exit"]
JobWebhookEvent = Literal["started", "finished"]
JobQueueReason = Literal["no_capacity", "budget", "max_parallel", "volume_busy"]

LIVE_JOB_STATUSES = frozenset({"queued", "starting", "running"})


class GpuCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    gpu_type: str
    gpu_count: int


class JobAttempt(BaseModel):
    """One attempt of a job; a retry starts a new one on a new machine."""

    model_config = ConfigDict(extra="allow")

    attempt: int
    deployment_id: Optional[str] = None
    status: JobStatus
    exit_code: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    cost_usd: Optional[float] = None
    gpu_type: str
    gpu_count: int
    region: Optional[str] = None


class Job(BaseModel):
    """A command run on its own fresh machine, which stops when the command ends.

    Env values are never in it, only ``env_keys``. ``webhook_secret`` is only set on the answer
    that created the job.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    status: JobStatus
    command: str
    gpu_type: str
    """The GPU it runs (or last ran) on; the first candidate until it has had a machine."""
    gpu_count: int
    gpu_candidates: list[GpuCandidate] = Field(default_factory=list)
    template: Optional[str] = None
    image: Optional[str] = None
    env_keys: list[str] = Field(default_factory=list)
    storage_id: Optional[str] = None
    max_runtime_minutes: int
    capacity_wait_minutes: int = 0
    queue_reason: Optional[JobQueueReason] = None
    next_attempt_at: Optional[datetime] = None
    attempt: int = 1
    max_retries: int = 0
    retry_on: list[JobRetryOn] = Field(default_factory=list)
    retry_exit_codes: list[int] = Field(default_factory=list)
    attempts: list[JobAttempt] = Field(default_factory=list)
    exit_code: Optional[int] = None
    error: Optional[str] = None
    instance_id: Optional[str] = None
    """The machine (an instance) the current attempt runs on."""
    environment_id: Optional[str] = None
    tags: dict[str, str] = Field(default_factory=dict)
    group_id: Optional[str] = None
    job_index: int = 0
    rerun_of: Optional[str] = None
    webhook_url: Optional[str] = None
    """The callback, shown as its host and the end of its path."""
    webhook_events: list[JobWebhookEvent] = Field(default_factory=list)
    webhook_secret: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    cost_per_hour: Optional[float] = None
    cost_usd: Optional[float] = None
    """Every attempt's machine, added up."""
    log_bytes: int = 0
    logs_truncated: bool = False
    code: Optional[dict[str, Any]] = None
    """``{"source": "upload", "ref", "sha256"}`` or ``{"source": "git", "url", "ref", "commit"}``."""
    allow_cpu_container: bool = False
    image_registry_auth: Optional[dict[str, str]] = None
    artifacts_count: int = 0
    gpu_util_avg: Optional[float] = None
    gpu_mem_peak_mb: Optional[float] = None

    @property
    def finished(self) -> bool:
        """Whether the job has ended (succeeded, failed, cancelled or timed out)."""
        return self.status not in LIVE_JOB_STATUSES


class JobGroup(BaseModel):
    """A group of jobs from ``count`` or ``params``. Its jobs are ``jobs.list(group_id=...)``."""

    model_config = ConfigDict(extra="allow")

    id: str
    count: int
    max_parallel: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    cost_usd: Optional[float] = None
    created_at: datetime


class SubmittedJobGroup(JobGroup):
    """A group as submitted, with its jobs."""

    jobs: list[Job] = Field(default_factory=list)
    webhook_secret: Optional[str] = None


class JobLogChunk(BaseModel):
    """A fragment of a job's combined output. ``seq`` and ``ts`` are None on a marker where output was dropped."""

    model_config = ConfigDict(extra="allow")

    seq: Optional[int] = None
    ts: Optional[datetime] = None
    text: str


class JobLogs(BaseModel):
    """One page of a job's output. Pass ``cursor`` back as ``after``; ``done`` once it ended and all was read."""

    model_config = ConfigDict(extra="allow")

    job_id: str
    status: JobStatus
    chunks: list[JobLogChunk]
    cursor: int
    truncated: bool = False
    done: bool


class JobEvent(BaseModel):
    """A moment in a job's life: ``created``, ``queued``, ``launch_attempt``, ``started``, ``exited`` and others."""

    model_config = ConfigDict(extra="allow")

    at: datetime
    kind: str
    detail: Optional[str] = None
    attempt: Optional[int] = None
    """The attempt it belongs to; None for a moment of the machine rather than of one attempt."""


class JobGpuSample(BaseModel):
    model_config = ConfigDict(extra="allow")

    util: float
    mem_used_mb: float
    mem_total_mb: float


class JobMetricPoint(BaseModel):
    """GPU use over one step while the command ran: ``util`` the average percent, memory its peak."""

    model_config = ConfigDict(extra="allow")

    at: datetime
    gpus: list[JobGpuSample]


class JobArtifact(BaseModel):
    """A file the command wrote to ``$RUNCRATE_OUTPUT_DIR``, kept 30 days after the job ended."""

    model_config = ConfigDict(extra="allow")

    path: str
    bytes: int
    sha256: str


class JobUpload(BaseModel):
    """Somewhere to PUT a job's code; run with ``code={"upload_id": ...}`` before ``expires_at``."""

    model_config = ConfigDict(extra="allow")

    upload_id: str
    url: Optional[str] = None
    """PUT the tar.gz here; None when a job already uses this upload (nothing to send)."""
    url_expires_at: Optional[datetime] = None
    expires_at: datetime
    max_bytes: int
