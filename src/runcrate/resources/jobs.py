"""Job resources: run a command on its own fresh GPU machine, follow it, and fetch its outputs.

Every submit and rerun sends an Idempotency-Key (a new one per call unless you pass your own),
and the call's retries reuse it, so a retry after a timeout answers the first job instead of
starting a second one.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import io
import os
import tarfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, List, Optional, Sequence, Union
from urllib.parse import quote

import httpx
from typing_extensions import Required, TypedDict, Unpack

from runcrate._exceptions import ApiError, ConnectionError, JobWaitTimeoutError
from runcrate._pagination import PaginatedResponse
from runcrate._transport import new_idempotency_key
from runcrate.models.jobs import (
    LIVE_JOB_STATUSES,
    Job,
    JobArtifact,
    JobEvent,
    JobGroup,
    JobLogChunk,
    JobLogs,
    JobMetricPoint,
    JobRetryOn,
    JobStatus,
    JobUpload,
    JobWebhookEvent,
    SubmittedJobGroup,
)
from runcrate.models.shared import ListMeta

_PATH = "/api/v1/jobs"
_GROUPS_PATH = "/api/v1/job-groups"
# A submit or rerun may take up to its route's 120 s while it launches: the client waits for the
# answer rather than giving up first (a retry would then only replay the same key).
_SUBMIT_TIMEOUT = 135.0
# The server holds a follow logs read for up to 25 s.
_FOLLOW_TIMEOUT = 40.0
# A group cancel stops every machine, each with a final volume copy-up (300 s route).
_GROUP_CANCEL_TIMEOUT = 315.0
# Left out of a directory uploaded as code.
_SKIPPED_DIRS = {".git", "__pycache__", "node_modules"}


class _JobFields(TypedDict, total=False):
    gpu_count: int
    """GPUs per machine (1 to 8) for ``gpu_type`` entries without a count. Default 1."""
    template: str
    image: str
    """A container image to run the command in, e.g. ``"pytorch/pytorch:latest"``."""
    env: dict[str, str]
    """Environment variables. Write-only: a job shows only ``env_keys``."""
    storage_id: str
    """A volume mounted at ``/workspace``."""
    name: str
    region: str
    """Only run here: a region id, the start of one such as ``us-east``, or a city or country."""
    capacity_wait_minutes: int
    """How long the job may wait for a GPU, 0 to 1440 minutes. Default 30."""
    max_retries: int
    """Retries of a failed attempt, 0 to 10. A machine failure is always retried once above 0."""
    retry_on: list[JobRetryOn]
    retry_exit_codes: list[int]
    tags: dict[str, str]
    webhook_url: Optional[str]
    """An https URL called with a signed POST when the job finishes (and starts, with webhook_events)."""
    webhook_events: list[JobWebhookEvent]
    code: dict[str, Any]
    """``{"upload_id": ...}`` from ``jobs.uploads.upload()``, or
    ``{"git": {"url": "https://...", "ref": "main", "token_env": "GIT_TOKEN"}}``."""
    image_registry_auth: dict[str, str]
    """``{"username_env": "NAME", "password_env": "NAME"}`` for a private ``image``."""
    allow_cpu_container: bool


class JobSpec(_JobFields, total=False):
    """The fields of one job."""

    command: Required[str]
    """Shell command, run with bash in ``/workspace``. At most 64 KB."""
    gpu_type: Required[Union[str, Sequence[str]]]
    """A GPU (``"A4000"``) or GPUs to try in order (``["H100", "A100-80GB:2"]``)."""
    max_runtime_minutes: Required[int]
    """1 to 10080 (7 days); each attempt stops after this long."""


class JobGroupSpec(JobSpec, total=False):
    """The fields of a group: ``count`` copies, or one job per ``params`` entry (merged over env)."""

    count: int
    params: list[dict[str, str]]
    max_parallel: int


class JobOverrides(_JobFields, total=False):
    """Fields to change on a rerun; ``env`` is merged over the job's own."""

    command: str
    gpu_type: Union[str, Sequence[str]]
    max_runtime_minutes: int


def _job_path(id: str, suffix: str = "") -> str:
    return f"{_PATH}/{quote(id, safe='')}{suffix}"


def _group_path(id: str, suffix: str = "") -> str:
    return f"{_GROUPS_PATH}/{quote(id, safe='')}{suffix}"


def _artifact_path(job_id: str, path: str) -> str:
    return _job_path(job_id, "/artifacts/" + quote(path, safe="/"))


def _spec_body(spec: Any) -> dict[str, Any]:
    body = {key: value for key, value in dict(spec).items() if value is not None}
    if isinstance(body.get("gpu_type"), (list, tuple)):
        body["gpu_type"] = list(body["gpu_type"])
    return body


def _list_params(
    *,
    status: Union[JobStatus, Sequence[JobStatus], None],
    tags: Optional[dict[str, str]],
    group_id: Optional[str],
    q: Optional[str],
    gpu_type: Optional[str],
    created_after: Union[datetime, str, None],
    limit: Optional[int],
    cursor: Optional[str],
) -> dict[str, Any]:
    if isinstance(created_after, datetime):
        if created_after.tzinfo is None:
            raise ValueError("created_after needs a timezone, e.g. datetime(..., tzinfo=timezone.utc)")
        created_after = created_after.isoformat()
    params: dict[str, Any] = {
        "status": status if isinstance(status, str) or status is None else ",".join(status),
        "tag": [f"{key}:{value}" for key, value in tags.items()] if tags else None,
        "group_id": group_id,
        "q": q,
        "gpu_type": gpu_type,
        "created_after": created_after,
        "limit": limit,
        "cursor": cursor,
    }
    return {key: value for key, value in params.items() if value is not None}


def _page(data: list[Job], meta: Any) -> PaginatedResponse[Job]:
    return PaginatedResponse(data=data, meta=ListMeta.model_validate(meta) if meta else None)


def _code_archive(source: Union[str, os.PathLike[str], bytes]) -> bytes:
    """The tar.gz to upload: given bytes, a .tar.gz file, or a directory packed here (regular
    files only, byte for byte the same for the same files)."""
    if isinstance(source, bytes):
        return source
    path = Path(source)
    if path.is_file():
        return path.read_bytes()
    if not path.is_dir():
        raise ValueError(f"{path} is neither a directory nor a .tar.gz file")
    # Only names, modes and contents go in (no owner, times or file name in the gzip header), so
    # the same files make the same bytes and the same sha256, which the upload dedupes on.
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=buffer, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in _SKIPPED_DIRS)
                for name in sorted(files):
                    full = Path(root) / name
                    if full.is_symlink() or not full.is_file():
                        continue
                    info = tarfile.TarInfo(full.relative_to(path).as_posix())
                    info.size = full.stat().st_size
                    info.mode = full.stat().st_mode & 0o777
                    info.mtime = 0
                    with full.open("rb") as file:
                        archive.addfile(info, file)
    return buffer.getvalue()


def _download_error(response: httpx.Response) -> ApiError:
    return ApiError(
        f"Downloading the file failed (HTTP {response.status_code})",
        status_code=response.status_code,
        code="download_failed",
        response=response,
    )


class _WaitClock:
    """The polls of ``wait``: the gap doubles from ``poll_interval`` to ``max_poll_interval``."""

    def __init__(self, timeout: Optional[float], poll_interval: float, max_poll_interval: float) -> None:
        self.timeout = timeout
        self.deadline = None if timeout is None else time.monotonic() + timeout
        self.gap = poll_interval
        self.max_gap = max_poll_interval

    def next_sleep(self, job: Job) -> float:
        """Seconds to sleep before the next poll; raises once the timeout has passed."""
        left = None if self.deadline is None else self.deadline - time.monotonic()
        if left is not None and left <= 0:
            raise JobWaitTimeoutError(f"Job {job.id} is still {job.status} after {self.timeout} s", job=job)
        gap = self.gap if left is None else min(self.gap, left)
        self.gap = min(self.gap * 2, self.max_gap)
        return gap


# ─── Sync ────────────────────────────────────────────────────────────────────


class JobArtifacts:
    """A job's outputs: the files its command wrote to ``$RUNCRATE_OUTPUT_DIR``."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def list(self, job_id: str) -> list[JobArtifact]:
        """The job's outputs by path, kept 30 days after it ended."""
        data, _ = self._transport.request("GET", _job_path(job_id, "/artifacts"), cast_to=list[JobArtifact])
        return data

    def url(self, job_id: str, path: str) -> str:
        """A signed URL that downloads one output, valid for an hour. Needs no API key."""
        return str(self._transport.redirect_location(_artifact_path(job_id, path)))

    def download(
        self, job_id: str, path: str, *, to: Union[str, os.PathLike[str], None] = None
    ) -> Union[bytes, Path]:
        """One output: its bytes, or streamed to the file ``to`` (replaced), whose path is returned."""
        url = self.url(job_id, path)
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, read=300.0)) as client:
                with client.stream("GET", url) as response:
                    if response.status_code >= 400:
                        raise _download_error(response)
                    if to is None:
                        return response.read()
                    target = Path(to)
                    with target.open("wb") as file:
                        for block in response.iter_bytes():
                            file.write(block)
                    return target
        except httpx.TransportError as e:
            raise ConnectionError(f"Downloading {path} failed: {e}") from e


class JobUploads:
    """Code uploads: a tar.gz a job unpacks into ``/workspace/code``, where its command runs."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def create(self, *, bytes: int, sha256: Optional[str] = None) -> JobUpload:
        """Somewhere to PUT a tar.gz of ``bytes`` (at most 1 GB). Use ``upload()`` for both steps."""
        body: dict[str, Any] = {"bytes": bytes}
        if sha256 is not None:
            body["sha256"] = sha256
        # The same hash answers the same upload, so a repeat makes no second one.
        data, _ = self._transport.request(
            "POST", f"{_PATH}/uploads", json=body, cast_to=JobUpload, idempotent=sha256 is not None
        )
        return data

    def upload(self, source: Union[str, os.PathLike[str], bytes]) -> JobUpload:
        """Uploads code and answers the upload; run a job with ``code={"upload_id": upload.upload_id}``.

        ``source`` is a directory (packed as a tar.gz without ``.git``, ``__pycache__`` and ``node_modules``), a
        .tar.gz file, or its bytes. The same archive again is not sent twice.
        """
        archive = _code_archive(source)
        upload = self.create(bytes=len(archive), sha256=hashlib.sha256(archive).hexdigest())
        if upload.url:
            try:
                response = httpx.put(upload.url, content=archive, timeout=httpx.Timeout(60.0, write=600.0))
            except httpx.TransportError as e:
                raise ConnectionError(f"Uploading the code failed: {e}") from e
            if response.status_code >= 400:
                raise ApiError(
                    f"Uploading the code failed (HTTP {response.status_code})",
                    status_code=response.status_code,
                    code="upload_failed",
                    response=response,
                )
        return upload


class Jobs:
    """Synchronous job operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport
        self.artifacts = JobArtifacts(transport)
        self.uploads = JobUploads(transport)

    def run(self, *, idempotency_key: Optional[str] = None, **spec: Unpack[JobSpec]) -> Job:
        """Run one job. Answers it queued or starting; ``wait()`` for the end.

        A low balance raises ``InsufficientCreditsError``, a reached environment budget the same
        with ``code == "BUDGET_REACHED"``, a bad field ``UnprocessableEntityError``. For several
        jobs at once use ``run_group()``.
        """
        if "count" in spec or "params" in spec:
            raise TypeError("jobs.run() runs one job: use jobs.run_group() for count or params")
        return self._submit(_PATH, _spec_body(spec), idempotency_key, Job)

    def run_group(self, *, idempotency_key: Optional[str] = None, **spec: Unpack[JobGroupSpec]) -> SubmittedJobGroup:
        """Run ``count`` copies of a job, or one per ``params`` entry, ``max_parallel`` at once."""
        return self._submit(_PATH, _spec_body(spec), idempotency_key, SubmittedJobGroup)

    def rerun(self, id: str, *, idempotency_key: Optional[str] = None, **overrides: Unpack[JobOverrides]) -> Job:
        """Run the job's spec again as a new job with its env values; ``env`` is merged over them.

        A field passed as None is sent as null (``webhook_url=None`` drops the callback). Only
        whoever submitted the job can reuse its env values; anyone else must send them.
        """
        return self._submit(_job_path(id, "/rerun"), dict(overrides), idempotency_key, Job)

    def _submit(self, path: str, body: dict[str, Any], idempotency_key: Optional[str], cast_to: Any) -> Any:
        data, _ = self._transport.request(
            "POST",
            path,
            json=body,
            cast_to=cast_to,
            idempotency_key=idempotency_key or new_idempotency_key(),
            idempotent=True,
            min_timeout=_SUBMIT_TIMEOUT,
        )
        return data

    def get(self, id: str) -> Job:
        data, _ = self._transport.request("GET", _job_path(id), cast_to=Job)
        return data

    def list(
        self,
        *,
        status: Union[JobStatus, Sequence[JobStatus], None] = None,
        tags: Optional[dict[str, str]] = None,
        group_id: Optional[str] = None,
        q: Optional[str] = None,
        gpu_type: Optional[str] = None,
        created_after: Union[datetime, str, None] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> PaginatedResponse[Job]:
        """One page of jobs, newest first (``limit`` 1 to 100, default 20). See ``list_all``."""
        params = _list_params(
            status=status, tags=tags, group_id=group_id, q=q, gpu_type=gpu_type,
            created_after=created_after, limit=limit, cursor=cursor,
        )
        data, meta = self._transport.request("GET", _PATH, params=params, cast_to=list[Job])
        return _page(data, meta)

    def list_all(
        self,
        *,
        status: Union[JobStatus, Sequence[JobStatus], None] = None,
        tags: Optional[dict[str, str]] = None,
        group_id: Optional[str] = None,
        q: Optional[str] = None,
        gpu_type: Optional[str] = None,
        created_after: Union[datetime, str, None] = None,
    ) -> Iterator[Job]:
        """Every job matching the filters, newest first, page by page."""
        cursor: Optional[str] = None
        while True:
            page = self.list(
                status=status, tags=tags, group_id=group_id, q=q, gpu_type=gpu_type,
                created_after=created_after, limit=100, cursor=cursor,
            )
            yield from page
            if not (page.has_more and page.cursor):
                return
            cursor = page.cursor

    def cancel(self, id: str) -> Job:
        """Stop the job's machine; it becomes ``cancelled``. A job that ended otherwise raises ``ConflictError``."""
        # Cancelling a cancelled job answers it unchanged, so a repeat is harmless.
        data, _ = self._transport.request(
            "POST", _job_path(id, "/cancel"), cast_to=Job, idempotent=True, min_timeout=_SUBMIT_TIMEOUT
        )
        return data

    def delete(self, id: str) -> None:
        """Delete a job that ended, with its logs and outputs. A live job raises ``ConflictError``."""
        self._transport.request("DELETE", _job_path(id))

    def logs(self, id: str, *, after: int = 0, limit: Optional[int] = None, follow: bool = False) -> JobLogs:
        """One page of output after ``after``; ``follow`` waits up to 25 s when there is none yet."""
        params: dict[str, Any] = {"after": after}
        if limit is not None:
            params["limit"] = limit
        if follow:
            params["follow"] = "true"
        data, _ = self._transport.request(
            "GET", _job_path(id, "/logs"), params=params, cast_to=JobLogs,
            min_timeout=_FOLLOW_TIMEOUT if follow else None,
        )
        return data

    def follow_logs(self, id: str, *, after: int = 0) -> Iterator[JobLogChunk]:
        """The job's output as it is written, chunk by chunk, until it ends and all was read."""
        while True:
            page = self.logs(id, after=after, follow=True)
            yield from page.chunks
            after = max(after, page.cursor)
            if page.done:
                return
            if not page.chunks:
                # The server holds an empty read open; one answered at once is spaced out.
                time.sleep(1.0)

    def events(self, id: str) -> List[JobEvent]:
        """The job's timeline, oldest first."""
        data, _ = self._transport.request("GET", _job_path(id, "/events"), cast_to=list[JobEvent])
        return data

    def metrics(self, id: str, *, step: Optional[int] = None) -> List[JobMetricPoint]:
        """GPU use while the command ran, one point per ``step`` seconds (60 to 86400)."""
        params = {"step": step} if step is not None else None
        data, _ = self._transport.request(
            "GET", _job_path(id, "/metrics"), params=params, cast_to=list[JobMetricPoint]
        )
        return data

    def wait(
        self,
        id: str,
        *,
        timeout: Optional[float] = None,
        poll_interval: float = 2.0,
        max_poll_interval: float = 30.0,
    ) -> Job:
        """Poll the job until it ends and answer it.

        The gap between polls starts at ``poll_interval`` seconds and doubles up to
        ``max_poll_interval``. Past ``timeout`` seconds (default: no limit) it raises
        ``JobWaitTimeoutError`` holding the job as last seen; the job keeps running.
        """
        clock = _WaitClock(timeout, poll_interval, max_poll_interval)
        while True:
            job = self.get(id)
            if job.status not in LIVE_JOB_STATUSES:
                return job
            time.sleep(clock.next_sleep(job))


class JobGroups:
    """Groups of jobs, made by ``jobs.run_group()``."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def get(self, id: str) -> JobGroup:
        data, _ = self._transport.request("GET", _group_path(id), cast_to=JobGroup)
        return data

    def cancel(self, id: str) -> JobGroup:
        """Cancel every job of the group that has not ended."""
        data, _ = self._transport.request(
            "POST", _group_path(id, "/cancel"), cast_to=JobGroup, idempotent=True,
            min_timeout=_GROUP_CANCEL_TIMEOUT,
        )
        return data


# ─── Async ───────────────────────────────────────────────────────────────────


class AsyncJobArtifacts:
    """A job's outputs. See ``JobArtifacts``."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list(self, job_id: str) -> list[JobArtifact]:
        data, _ = await self._transport.request(
            "GET", _job_path(job_id, "/artifacts"), cast_to=list[JobArtifact]
        )
        return data

    async def url(self, job_id: str, path: str) -> str:
        return str(await self._transport.redirect_location(_artifact_path(job_id, path)))

    async def download(
        self, job_id: str, path: str, *, to: Union[str, os.PathLike[str], None] = None
    ) -> Union[bytes, Path]:
        """One output: its bytes, or streamed to the file ``to`` (replaced), whose path is returned."""
        url = await self.url(job_id, path)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=300.0)) as client:
                async with client.stream("GET", url) as response:
                    if response.status_code >= 400:
                        raise _download_error(response)
                    if to is None:
                        return await response.aread()
                    target = Path(to)
                    with target.open("wb") as file:
                        async for block in response.aiter_bytes():
                            file.write(block)
                    return target
        except httpx.TransportError as e:
            raise ConnectionError(f"Downloading {path} failed: {e}") from e


class AsyncJobUploads:
    """Code uploads. See ``JobUploads``."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def create(self, *, bytes: int, sha256: Optional[str] = None) -> JobUpload:
        body: dict[str, Any] = {"bytes": bytes}
        if sha256 is not None:
            body["sha256"] = sha256
        data, _ = await self._transport.request(
            "POST", f"{_PATH}/uploads", json=body, cast_to=JobUpload, idempotent=sha256 is not None
        )
        return data

    async def upload(self, source: Union[str, os.PathLike[str], bytes]) -> JobUpload:
        """Uploads code and answers the upload. See ``JobUploads.upload``."""
        archive = await asyncio.to_thread(_code_archive, source)
        upload = await self.create(bytes=len(archive), sha256=hashlib.sha256(archive).hexdigest())
        if upload.url:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, write=600.0)) as client:
                    response = await client.put(upload.url, content=archive)
            except httpx.TransportError as e:
                raise ConnectionError(f"Uploading the code failed: {e}") from e
            if response.status_code >= 400:
                raise ApiError(
                    f"Uploading the code failed (HTTP {response.status_code})",
                    status_code=response.status_code,
                    code="upload_failed",
                    response=response,
                )
        return upload


class AsyncJobs:
    """Asynchronous job operations. See ``Jobs``."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport
        self.artifacts = AsyncJobArtifacts(transport)
        self.uploads = AsyncJobUploads(transport)

    async def run(self, *, idempotency_key: Optional[str] = None, **spec: Unpack[JobSpec]) -> Job:
        if "count" in spec or "params" in spec:
            raise TypeError("jobs.run() runs one job: use jobs.run_group() for count or params")
        return await self._submit(_PATH, _spec_body(spec), idempotency_key, Job)

    async def run_group(
        self, *, idempotency_key: Optional[str] = None, **spec: Unpack[JobGroupSpec]
    ) -> SubmittedJobGroup:
        return await self._submit(_PATH, _spec_body(spec), idempotency_key, SubmittedJobGroup)

    async def rerun(
        self, id: str, *, idempotency_key: Optional[str] = None, **overrides: Unpack[JobOverrides]
    ) -> Job:
        return await self._submit(_job_path(id, "/rerun"), dict(overrides), idempotency_key, Job)

    async def _submit(
        self, path: str, body: dict[str, Any], idempotency_key: Optional[str], cast_to: Any
    ) -> Any:
        data, _ = await self._transport.request(
            "POST",
            path,
            json=body,
            cast_to=cast_to,
            idempotency_key=idempotency_key or new_idempotency_key(),
            idempotent=True,
            min_timeout=_SUBMIT_TIMEOUT,
        )
        return data

    async def get(self, id: str) -> Job:
        data, _ = await self._transport.request("GET", _job_path(id), cast_to=Job)
        return data

    async def list(
        self,
        *,
        status: Union[JobStatus, Sequence[JobStatus], None] = None,
        tags: Optional[dict[str, str]] = None,
        group_id: Optional[str] = None,
        q: Optional[str] = None,
        gpu_type: Optional[str] = None,
        created_after: Union[datetime, str, None] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> PaginatedResponse[Job]:
        params = _list_params(
            status=status, tags=tags, group_id=group_id, q=q, gpu_type=gpu_type,
            created_after=created_after, limit=limit, cursor=cursor,
        )
        data, meta = await self._transport.request("GET", _PATH, params=params, cast_to=list[Job])
        return _page(data, meta)

    async def list_all(
        self,
        *,
        status: Union[JobStatus, Sequence[JobStatus], None] = None,
        tags: Optional[dict[str, str]] = None,
        group_id: Optional[str] = None,
        q: Optional[str] = None,
        gpu_type: Optional[str] = None,
        created_after: Union[datetime, str, None] = None,
    ) -> AsyncIterator[Job]:
        cursor: Optional[str] = None
        while True:
            page = await self.list(
                status=status, tags=tags, group_id=group_id, q=q, gpu_type=gpu_type,
                created_after=created_after, limit=100, cursor=cursor,
            )
            for job in page:
                yield job
            if not (page.has_more and page.cursor):
                return
            cursor = page.cursor

    async def cancel(self, id: str) -> Job:
        data, _ = await self._transport.request(
            "POST", _job_path(id, "/cancel"), cast_to=Job, idempotent=True, min_timeout=_SUBMIT_TIMEOUT
        )
        return data

    async def delete(self, id: str) -> None:
        await self._transport.request("DELETE", _job_path(id))

    async def logs(
        self, id: str, *, after: int = 0, limit: Optional[int] = None, follow: bool = False
    ) -> JobLogs:
        params: dict[str, Any] = {"after": after}
        if limit is not None:
            params["limit"] = limit
        if follow:
            params["follow"] = "true"
        data, _ = await self._transport.request(
            "GET", _job_path(id, "/logs"), params=params, cast_to=JobLogs,
            min_timeout=_FOLLOW_TIMEOUT if follow else None,
        )
        return data

    async def follow_logs(self, id: str, *, after: int = 0) -> AsyncIterator[JobLogChunk]:
        while True:
            page = await self.logs(id, after=after, follow=True)
            for chunk in page.chunks:
                yield chunk
            after = max(after, page.cursor)
            if page.done:
                return
            if not page.chunks:
                await asyncio.sleep(1.0)

    async def events(self, id: str) -> List[JobEvent]:
        data, _ = await self._transport.request("GET", _job_path(id, "/events"), cast_to=list[JobEvent])
        return data

    async def metrics(self, id: str, *, step: Optional[int] = None) -> List[JobMetricPoint]:
        params = {"step": step} if step is not None else None
        data, _ = await self._transport.request(
            "GET", _job_path(id, "/metrics"), params=params, cast_to=list[JobMetricPoint]
        )
        return data

    async def wait(
        self,
        id: str,
        *,
        timeout: Optional[float] = None,
        poll_interval: float = 2.0,
        max_poll_interval: float = 30.0,
    ) -> Job:
        """Poll the job until it ends. See ``Jobs.wait``."""
        clock = _WaitClock(timeout, poll_interval, max_poll_interval)
        while True:
            job = await self.get(id)
            if job.status not in LIVE_JOB_STATUSES:
                return job
            await asyncio.sleep(clock.next_sleep(job))


class AsyncJobGroups:
    """Groups of jobs. See ``JobGroups``."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def get(self, id: str) -> JobGroup:
        data, _ = await self._transport.request("GET", _group_path(id), cast_to=JobGroup)
        return data

    async def cancel(self, id: str) -> JobGroup:
        data, _ = await self._transport.request(
            "POST", _group_path(id, "/cancel"), cast_to=JobGroup, idempotent=True,
            min_timeout=_GROUP_CANCEL_TIMEOUT,
        )
        return data


__all__ = [
    "AsyncJobArtifacts",
    "AsyncJobGroups",
    "AsyncJobUploads",
    "AsyncJobs",
    "JobArtifacts",
    "JobGroupSpec",
    "JobGroups",
    "JobOverrides",
    "JobSpec",
    "JobUploads",
    "Jobs",
]
