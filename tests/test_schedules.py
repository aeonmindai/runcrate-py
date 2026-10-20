"""Tests for schedules resource."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from runcrate import (
    AsyncRuncrate,
    ConflictError,
    InsufficientCreditsError,
    Runcrate,
    UnprocessableEntityError,
)

_JOB_SPEC = {"command": "python train.py", "gpu_type": "H100", "max_runtime_minutes": 120}

_SCHEDULE = {
    "id": "sch-1",
    "name": "nightly-train",
    "kind": "job",
    "environment_id": "env-1",
    "created_by": "user-1",
    "run_as": "user-1",
    "run_as_credential": "api_key",
    "spec": {**_JOB_SPEC, "env_keys": ["HF_TOKEN"]},
    "max_runtime_minutes": 120,
    "run_at": None,
    "cron": "0 2 * * *",
    "timezone": "Europe/London",
    "overlap": "skip",
    "enabled": True,
    "next_run_at": "2026-10-21T01:00:00.000Z",
    "last_run_at": None,
    "last_status": None,
    "last_error": None,
    "last_instance_id": None,
    "last_job_id": None,
    "run_count": 0,
    "created_at": "2026-10-20T10:00:00.000Z",
    "updated_at": "2026-10-20T10:00:00.000Z",
}


def _body(route: respx.Route) -> dict:
    return json.loads(route.calls[0].request.content)


class TestCreate:
    def test_recurring_sends_cron_and_parses_schedule(
        self, client: Runcrate, mock_api: respx.MockRouter
    ):
        route = mock_api.post("/api/v1/schedules").mock(
            return_value=httpx.Response(201, json={"data": _SCHEDULE})
        )

        schedule = client.schedules.create(
            kind="job",
            spec=_JOB_SPEC,
            cron="0 2 * * *",
            timezone="Europe/London",
            overlap="skip",
            name="nightly-train",
        )

        assert _body(route) == {
            "kind": "job",
            "spec": _JOB_SPEC,
            "cron": "0 2 * * *",
            "timezone": "Europe/London",
            "overlap": "skip",
            "name": "nightly-train",
        }
        assert schedule.id == "sch-1"
        assert schedule.cron == "0 2 * * *"
        assert schedule.run_at is None
        assert schedule.next_run_at == datetime(2026, 10, 21, 1, 0, tzinfo=timezone.utc)
        assert schedule.spec["env_keys"] == ["HF_TOKEN"]

    def test_run_at_aware_datetime_is_sent_as_utc_instant(
        self, client: Runcrate, mock_api: respx.MockRouter
    ):
        route = mock_api.post("/api/v1/schedules").mock(
            return_value=httpx.Response(201, json={"data": _SCHEDULE})
        )
        london_summer = timezone(timedelta(hours=1))

        client.schedules.create(
            kind="instance",
            spec={"name": "eval-box", "gpu_type": "A100", "max_runtime_minutes": 60},
            run_at=datetime(2026, 10, 21, 2, 0, tzinfo=london_summer),
        )

        body = _body(route)
        assert body["run_at"] == "2026-10-21T01:00:00.000Z"
        assert "cron" not in body

    @pytest.mark.parametrize(
        "run_at",
        ["2026-10-21T01:00:00Z", "2026-10-21T03:00:00+02:00", "2026-10-21T01:00:00.000Z"],
    )
    def test_run_at_iso_string_with_offset_is_normalised(
        self, client: Runcrate, mock_api: respx.MockRouter, run_at: str
    ):
        route = mock_api.post("/api/v1/schedules").mock(
            return_value=httpx.Response(201, json={"data": _SCHEDULE})
        )

        client.schedules.create(kind="job", spec=_JOB_SPEC, run_at=run_at)

        assert _body(route)["run_at"] == "2026-10-21T01:00:00.000Z"

    @pytest.mark.parametrize("run_at", [datetime(2026, 10, 21, 2, 0), "2026-10-21T02:00:00"])
    def test_naive_run_at_is_refused_before_any_request(
        self, client: Runcrate, mock_api: respx.MockRouter, run_at: datetime | str
    ):
        # No route is mocked, so a request would fail the test with a respx error.
        with pytest.raises(ValueError, match="no timezone"):
            client.schedules.create(kind="job", spec=_JOB_SPEC, run_at=run_at)

    def test_unparseable_run_at_is_refused(self, client: Runcrate):
        with pytest.raises(ValueError, match="ISO 8601"):
            client.schedules.create(kind="job", spec=_JOB_SPEC, run_at="tomorrow at 2")

    def test_needs_exactly_one_of_run_at_or_cron(self, client: Runcrate):
        with pytest.raises(ValueError, match="exactly one"):
            client.schedules.create(kind="job", spec=_JOB_SPEC)
        with pytest.raises(ValueError, match="exactly one"):
            client.schedules.create(
                kind="job", spec=_JOB_SPEC, run_at="2026-10-21T01:00:00Z", cron="0 2 * * *"
            )

    def test_validation_error_is_mapped(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/schedules").mock(
            return_value=httpx.Response(
                422,
                json={
                    "error": {
                        "code": "validation_error",
                        "message": "Runs must be at least 15 minutes apart.",
                        "details": {"field": "cron"},
                    }
                },
            )
        )

        with pytest.raises(UnprocessableEntityError) as exc:
            client.schedules.create(kind="job", spec=_JOB_SPEC, cron="*/5 * * * *")

        assert exc.value.code == "validation_error"
        assert exc.value.details == {"field": "cron"}

    def test_schedule_cap_is_a_conflict(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/schedules").mock(
            return_value=httpx.Response(
                409,
                json={"error": {"code": "conflict", "message": "At most 50 schedules here."}},
            )
        )

        with pytest.raises(ConflictError):
            client.schedules.create(kind="job", spec=_JOB_SPEC, cron="0 2 * * *")


class TestReadAndChange:
    def test_list(self, client: Runcrate, mock_api: respx.MockRouter):
        one_off = {
            **_SCHEDULE,
            "id": "sch-2",
            "cron": None,
            "run_at": "2026-10-22T09:00:00.000Z",
            "next_run_at": None,
            "last_run_at": "2026-10-22T09:01:30.000Z",
            "last_status": "skipped_budget",
            "last_error": "Monthly budget reached",
            "run_count": 1,
        }
        mock_api.get("/api/v1/schedules").mock(
            return_value=httpx.Response(200, json={"data": [one_off, _SCHEDULE]})
        )

        schedules = client.schedules.list()

        assert [s.id for s in schedules] == ["sch-2", "sch-1"]
        assert schedules[0].run_at == datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
        assert schedules[0].last_status == "skipped_budget"
        assert schedules[0].run_count == 1

    def test_parses_run_as_and_credential_revoked(
        self, client: Runcrate, mock_api: respx.MockRouter
    ):
        paused = {
            **_SCHEDULE,
            "run_as": "user-2",
            "run_as_credential": "agent",
            "enabled": False,
            "next_run_at": None,
            "last_status": "credential_revoked",
            "last_error": "The agent sign-in this schedule runs with has ended.",
        }
        mock_api.get("/api/v1/schedules/sch-1").mock(
            return_value=httpx.Response(200, json={"data": paused})
        )

        schedule = client.schedules.get("sch-1")

        assert schedule.run_as == "user-2"
        assert schedule.run_as_credential == "agent"
        assert schedule.last_status == "credential_revoked"
        assert schedule.enabled is False

    def test_get_quotes_the_id(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.get("/api/v1/schedules/a%2Fb").mock(
            return_value=httpx.Response(200, json={"data": _SCHEDULE})
        )

        assert client.schedules.get("a/b").name == "nightly-train"
        assert route.called

    def test_update_sends_only_given_fields(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.patch("/api/v1/schedules/sch-1").mock(
            return_value=httpx.Response(
                200, json={"data": {**_SCHEDULE, "enabled": False, "next_run_at": None}}
            )
        )

        schedule = client.schedules.update("sch-1", enabled=False)

        assert _body(route) == {"enabled": False}
        assert schedule.enabled is False
        assert schedule.next_run_at is None

    def test_update_run_at_switches_to_one_off(
        self, client: Runcrate, mock_api: respx.MockRouter
    ):
        route = mock_api.patch("/api/v1/schedules/sch-1").mock(
            return_value=httpx.Response(200, json={"data": _SCHEDULE})
        )

        client.schedules.update("sch-1", run_at="2026-10-23T08:00:00+00:00", name="once")

        assert _body(route) == {"run_at": "2026-10-23T08:00:00.000Z", "name": "once"}

    def test_update_refuses_naive_run_at(self, client: Runcrate):
        with pytest.raises(ValueError, match="no timezone"):
            client.schedules.update("sch-1", run_at=datetime(2026, 10, 23, 8, 0))

    def test_update_refuses_run_at_and_cron_together(self, client: Runcrate):
        with pytest.raises(ValueError, match="not both"):
            client.schedules.update(
                "sch-1", run_at="2026-10-23T08:00:00Z", cron="0 2 * * *"
            )

    def test_update_needs_a_field(self, client: Runcrate):
        with pytest.raises(ValueError, match="Nothing to update"):
            client.schedules.update("sch-1")

    def test_delete(self, client: Runcrate, mock_api: respx.MockRouter):
        route = mock_api.delete("/api/v1/schedules/sch-1").mock(
            return_value=httpx.Response(200, json={"data": {"id": "sch-1", "deleted": True}})
        )

        assert client.schedules.delete("sch-1") is None
        assert route.called


class TestRunNow:
    def test_parses_schedule_and_launched_job(
        self, client: Runcrate, mock_api: respx.MockRouter
    ):
        route = mock_api.post("/api/v1/schedules/sch-1/run-now").mock(
            return_value=httpx.Response(
                201,
                json={
                    "data": {
                        "schedule": {
                            **_SCHEDULE,
                            "last_status": "launched",
                            "last_job_id": "job-9",
                            "run_count": 1,
                        },
                        "job": {"id": "job-9", "status": "queued"},
                    }
                },
            )
        )

        run = client.schedules.run_now("sch-1")

        assert route.calls[0].request.content in (b"", None)
        assert run.schedule.last_status == "launched"
        assert run.schedule.last_job_id == "job-9"
        assert run.job == {"id": "job-9", "status": "queued"}
        assert run.instance is None

    def test_parses_launched_instance(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/schedules/sch-1/run-now").mock(
            return_value=httpx.Response(
                201,
                json={
                    "data": {
                        "schedule": {**_SCHEDULE, "kind": "instance"},
                        "instance": {"id": "inst-7", "name": "eval-box", "status": "deploying"},
                    }
                },
            )
        )

        run = client.schedules.run_now("sch-1")

        assert run.instance is not None
        assert run.instance.id == "inst-7"
        assert run.job is None

    def test_budget_reached_surfaces_code(self, client: Runcrate, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/schedules/sch-1/run-now").mock(
            return_value=httpx.Response(
                402,
                json={
                    "error": {
                        "code": "BUDGET_REACHED",
                        "message": "This environment reached its $500.00 monthly budget.",
                    }
                },
            )
        )

        with pytest.raises(InsufficientCreditsError) as exc:
            client.schedules.run_now("sch-1")

        assert exc.value.status_code == 402
        assert exc.value.code == "BUDGET_REACHED"
        assert "monthly budget" in exc.value.message


class TestAsync:
    async def test_create_list_update_run_now_delete(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter
    ):
        create = mock_api.post("/api/v1/schedules").mock(
            return_value=httpx.Response(201, json={"data": _SCHEDULE})
        )
        mock_api.get("/api/v1/schedules").mock(
            return_value=httpx.Response(200, json={"data": [_SCHEDULE]})
        )
        mock_api.get("/api/v1/schedules/sch-1").mock(
            return_value=httpx.Response(200, json={"data": _SCHEDULE})
        )
        update = mock_api.patch("/api/v1/schedules/sch-1").mock(
            return_value=httpx.Response(200, json={"data": {**_SCHEDULE, "overlap": "allow"}})
        )
        mock_api.post("/api/v1/schedules/sch-1/run-now").mock(
            return_value=httpx.Response(
                201, json={"data": {"schedule": _SCHEDULE, "job": {"id": "job-1"}}}
            )
        )
        delete = mock_api.delete("/api/v1/schedules/sch-1").mock(
            return_value=httpx.Response(200, json={"data": {"id": "sch-1", "deleted": True}})
        )

        async with AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=0) as client:
            created = await client.schedules.create(
                kind="job",
                spec=_JOB_SPEC,
                run_at=datetime(2026, 10, 21, 1, 0, tzinfo=timezone.utc),
            )
            listed = await client.schedules.list()
            fetched = await client.schedules.get("sch-1")
            updated = await client.schedules.update("sch-1", overlap="allow")
            run = await client.schedules.run_now("sch-1")
            await client.schedules.delete("sch-1")

        assert _body(create)["run_at"] == "2026-10-21T01:00:00.000Z"
        assert created.id == listed[0].id == fetched.id == "sch-1"
        assert _body(update) == {"overlap": "allow"}
        assert updated.overlap == "allow"
        assert run.job == {"id": "job-1"}
        assert delete.called

    async def test_naive_run_at_is_refused(self, api_key: str, base_url: str):
        async with AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=0) as client:
            with pytest.raises(ValueError, match="no timezone"):
                await client.schedules.create(
                    kind="job", spec=_JOB_SPEC, run_at=datetime(2026, 10, 21, 2, 0)
                )

    async def test_budget_reached(self, api_key: str, base_url: str, mock_api: respx.MockRouter):
        mock_api.post("/api/v1/schedules/sch-1/run-now").mock(
            return_value=httpx.Response(
                402, json={"error": {"code": "BUDGET_REACHED", "message": "Budget reached."}}
            )
        )

        async with AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=0) as client:
            with pytest.raises(InsufficientCreditsError) as exc:
                await client.schedules.run_now("sch-1")

        assert exc.value.code == "BUDGET_REACHED"
