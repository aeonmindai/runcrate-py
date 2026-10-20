"""Schedule resources: start an instance or a job later, once or on a recurring cron."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone as tz
from typing import Any, Optional, Union
from urllib.parse import quote

from runcrate.models.schedules import (
    Schedule,
    ScheduleCreate,
    ScheduleKind,
    ScheduleOverlap,
    ScheduleRun,
    ScheduleUpdate,
)

_PATH = "/api/v1/schedules"


def _path(id: str, suffix: str = "") -> str:
    return f"{_PATH}/{quote(id, safe='')}{suffix}"


def _iso_instant(run_at: Union[datetime, str]) -> str:
    """Turn ``run_at`` into a UTC ISO 8601 instant, refusing values without a timezone."""
    if isinstance(run_at, str):
        text = run_at.strip()
        if text[-1:] in ("Z", "z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            raise ValueError(
                f"run_at must be an ISO 8601 time with an offset, such as "
                f"'2026-10-21T02:00:00+01:00' or '2026-10-21T01:00:00Z'. Got {run_at!r}."
            ) from None
    else:
        parsed = run_at
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            "run_at has no timezone, so the launch time is ambiguous. Pass a timezone-aware "
            "datetime, such as datetime(2026, 10, 21, 2, 0, tzinfo=ZoneInfo('Europe/London')), "
            "or an ISO string with an offset."
        )
    return parsed.astimezone(tz.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _create_body(
    *,
    kind: ScheduleKind,
    spec: dict[str, Any],
    run_at: Optional[Union[datetime, str]],
    cron: Optional[str],
    timezone: Optional[str],
    overlap: Optional[ScheduleOverlap],
    name: Optional[str],
    enabled: Optional[bool],
) -> dict[str, Any]:
    if (run_at is None) == (cron is None):
        raise ValueError("Pass exactly one of run_at (a one-off launch) or cron (a recurring one).")
    return ScheduleCreate(
        kind=kind,
        spec=spec,
        run_at=None if run_at is None else _iso_instant(run_at),
        cron=cron,
        timezone=timezone,
        overlap=overlap,
        name=name,
        enabled=enabled,
    ).model_dump(exclude_none=True)


def _update_body(
    *,
    enabled: Optional[bool],
    run_at: Optional[Union[datetime, str]],
    cron: Optional[str],
    timezone: Optional[str],
    overlap: Optional[ScheduleOverlap],
    name: Optional[str],
    spec: Optional[dict[str, Any]],
) -> dict[str, Any]:
    if run_at is not None and cron is not None:
        raise ValueError(
            "Pass run_at to switch to a one-off launch or cron to switch to a recurring one, "
            "not both."
        )
    body = ScheduleUpdate(
        enabled=enabled,
        run_at=None if run_at is None else _iso_instant(run_at),
        cron=cron,
        timezone=timezone,
        overlap=overlap,
        name=name,
        spec=spec,
    ).model_dump(exclude_none=True)
    if not body:
        raise ValueError(
            "Nothing to update. Pass at least one of enabled, run_at, cron, timezone, overlap, "
            "name or spec."
        )
    return body


class Schedules:
    """Synchronous schedule operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def create(
        self,
        *,
        kind: ScheduleKind,
        spec: dict[str, Any],
        run_at: Optional[Union[datetime, str]] = None,
        cron: Optional[str] = None,
        timezone: Optional[str] = None,
        overlap: Optional[ScheduleOverlap] = None,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Schedule:
        """Schedule an instance or a job to start later.

        Args:
            kind: ``"instance"`` or ``"job"``.
            spec: The create body of that kind, exactly what ``POST /api/v1/instances`` or
                ``POST /api/v1/jobs`` takes. ``max_runtime_minutes`` is required.
            run_at: Start once at this time. A timezone-aware datetime or an ISO string with
                an offset; values without a timezone raise ``ValueError``.
            cron: Start on this 5-field cron (``"0 2 * * *"``), read in ``timezone``. Runs
                must be at least 15 minutes apart. Pass exactly one of ``run_at`` or ``cron``.
            timezone: IANA timezone such as ``"Europe/London"``. Defaults to UTC.
            overlap: ``"skip"`` (default) skips a recurring run while the previous one is
                still live; ``"allow"`` starts it anyway.
            name: Schedule name. Defaults to the spec's name.
            enabled: Create it paused with ``False``.
        """
        body = _create_body(
            kind=kind,
            spec=spec,
            run_at=run_at,
            cron=cron,
            timezone=timezone,
            overlap=overlap,
            name=name,
            enabled=enabled,
        )
        data, _ = self._transport.request("POST", _PATH, json=body, cast_to=Schedule)
        return data

    def list(self) -> list[Schedule]:
        """Schedules in the current environment, newest first."""
        data, _ = self._transport.request("GET", _PATH, cast_to=list[Schedule])
        return data

    def get(self, id: str) -> Schedule:
        data, _ = self._transport.request("GET", _path(id), cast_to=Schedule)
        return data

    def update(
        self,
        id: str,
        *,
        enabled: Optional[bool] = None,
        run_at: Optional[Union[datetime, str]] = None,
        cron: Optional[str] = None,
        timezone: Optional[str] = None,
        overlap: Optional[ScheduleOverlap] = None,
        name: Optional[str] = None,
        spec: Optional[dict[str, Any]] = None,
    ) -> Schedule:
        """Change a schedule. Only the arguments you pass are sent.

        ``enabled=False`` pauses it and ``enabled=True`` resumes it. ``run_at`` turns it into a
        one-off and ``cron`` into a recurring schedule. ``spec`` replaces the whole spec, so
        send env values again.
        """
        body = _update_body(
            enabled=enabled,
            run_at=run_at,
            cron=cron,
            timezone=timezone,
            overlap=overlap,
            name=name,
            spec=spec,
        )
        data, _ = self._transport.request("PATCH", _path(id), json=body, cast_to=Schedule)
        return data

    def delete(self, id: str) -> None:
        self._transport.request("DELETE", _path(id))

    def run_now(self, id: str) -> ScheduleRun:
        """Launch the schedule's spec now, paused or not. ``next_run_at`` does not move."""
        data, _ = self._transport.request("POST", _path(id, "/run-now"), cast_to=ScheduleRun)
        return data


class AsyncSchedules:
    """Asynchronous schedule operations."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        kind: ScheduleKind,
        spec: dict[str, Any],
        run_at: Optional[Union[datetime, str]] = None,
        cron: Optional[str] = None,
        timezone: Optional[str] = None,
        overlap: Optional[ScheduleOverlap] = None,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Schedule:
        """Schedule an instance or a job to start later. See ``Schedules.create``."""
        body = _create_body(
            kind=kind,
            spec=spec,
            run_at=run_at,
            cron=cron,
            timezone=timezone,
            overlap=overlap,
            name=name,
            enabled=enabled,
        )
        data, _ = await self._transport.request("POST", _PATH, json=body, cast_to=Schedule)
        return data

    async def list(self) -> list[Schedule]:
        """Schedules in the current environment, newest first."""
        data, _ = await self._transport.request("GET", _PATH, cast_to=list[Schedule])
        return data

    async def get(self, id: str) -> Schedule:
        data, _ = await self._transport.request("GET", _path(id), cast_to=Schedule)
        return data

    async def update(
        self,
        id: str,
        *,
        enabled: Optional[bool] = None,
        run_at: Optional[Union[datetime, str]] = None,
        cron: Optional[str] = None,
        timezone: Optional[str] = None,
        overlap: Optional[ScheduleOverlap] = None,
        name: Optional[str] = None,
        spec: Optional[dict[str, Any]] = None,
    ) -> Schedule:
        """Change a schedule. Only the arguments you pass are sent. See ``Schedules.update``."""
        body = _update_body(
            enabled=enabled,
            run_at=run_at,
            cron=cron,
            timezone=timezone,
            overlap=overlap,
            name=name,
            spec=spec,
        )
        data, _ = await self._transport.request("PATCH", _path(id), json=body, cast_to=Schedule)
        return data

    async def delete(self, id: str) -> None:
        await self._transport.request("DELETE", _path(id))

    async def run_now(self, id: str) -> ScheduleRun:
        """Launch the schedule's spec now, paused or not. ``next_run_at`` does not move."""
        data, _ = await self._transport.request(
            "POST", _path(id, "/run-now"), cast_to=ScheduleRun
        )
        return data
