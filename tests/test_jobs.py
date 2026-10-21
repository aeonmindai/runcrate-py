"""Tests for the jobs resources and the retry rules of creates (RUN-533, RUN-548)."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from runcrate import (
    AsyncRuncrate,
    ConflictError,
    ConnectionError,
    JobWaitTimeoutError,
    Runcrate,
    TimeoutError,
)

JOB_ID = "6f1c2d3e-4b5a-4c6d-8e7f-901234567890"


def _job(**overrides: Any) -> dict[str, Any]:
    return {
        "id": JOB_ID,
        "name": "train",
        "status": "queued",
        "command": "python train.py",
        "gpu_type": "A4000",
        "gpu_count": 1,
        "gpu_candidates": [{"gpu_type": "A4000", "gpu_count": 1}],
        "env_keys": ["HF_TOKEN"],
        "max_runtime_minutes": 5,
        "tags": {"run_id": "r-1"},
        "created_at": "2026-10-21T10:00:00Z",
        **overrides,
    }


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr("runcrate._transport.time.sleep", slept.append)
    monkeypatch.setattr("runcrate.resources.jobs.time.sleep", slept.append)
    return slept


def _client(api_key: str, base_url: str, max_retries: int = 2) -> Runcrate:
    return Runcrate(api_key=api_key, base_url=base_url, max_retries=max_retries)


def _key(call: Any) -> str:
    return str(call.request.headers.get("idempotency-key"))


class TestRun:
    def test_sends_every_field_as_given(self, client: Runcrate, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/jobs").mock(return_value=httpx.Response(201, json={"data": {
            "id": "g1", "count": 2, "max_parallel": 1, "status_counts": {"queued": 2},
            "created_at": "2026-10-21T10:00:00Z", "jobs": [_job(), _job(job_index=1)],
        }}))
        group = client.jobs.run_group(
            command="python sweep.py",
            gpu_type=("H100", "A100-80GB:2"),
            max_runtime_minutes=30,
            env={"HF_TOKEN": "x"},
            tags={"run_id": "1"},
            params=[{"LR": "0.1"}, {"LR": "0.2"}],
            max_parallel=1,
            code={"git": {"url": "https://github.com/a/b", "token_env": "GIT_TOKEN"}},
            max_retries=2,
            retry_on=["nonzero_exit"],
        )
        assert json.loads(route.calls[0].request.content) == {
            "command": "python sweep.py",
            "gpu_type": ["H100", "A100-80GB:2"],
            "max_runtime_minutes": 30,
            "env": {"HF_TOKEN": "x"},
            "tags": {"run_id": "1"},
            "params": [{"LR": "0.1"}, {"LR": "0.2"}],
            "max_parallel": 1,
            "code": {"git": {"url": "https://github.com/a/b", "token_env": "GIT_TOKEN"}},
            "max_retries": 2,
            "retry_on": ["nonzero_exit"],
        }
        assert group.status_counts == {"queued": 2}
        assert [j.job_index for j in group.jobs] == [0, 1]

    def test_one_key_per_call_reused_on_its_retries(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        route = mock_api.post("/api/v1/jobs").mock(side_effect=[
            httpx.Response(500, json={"error": {"code": "internal_error", "message": "oops"}}),
            httpx.Response(201, json={"data": _job()}),
            httpx.Response(201, json={"data": _job()}),
        ])
        client = _client(api_key, base_url, max_retries=1)
        client.jobs.run(command="x", gpu_type="A4000", max_runtime_minutes=5)
        client.jobs.run(command="x", gpu_type="A4000", max_runtime_minutes=5)
        keys = [_key(c) for c in route.calls]
        assert len(keys[0]) == 36
        assert keys[1] == keys[0]
        assert keys[2] != keys[0]

    def test_retried_after_a_read_timeout_with_the_same_key(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        route = mock_api.post("/api/v1/jobs").mock(side_effect=[
            httpx.ReadTimeout("slow"),
            httpx.Response(200, json={"data": _job()}, headers={"Idempotent-Replayed": "true"}),
        ])
        job = _client(api_key, base_url).jobs.run(
            command="x", gpu_type="A4000", max_runtime_minutes=5, idempotency_key="my-key"
        )
        assert job.id == JOB_ID
        assert [_key(c) for c in route.calls] == ["my-key", "my-key"]

    def test_asks_again_while_the_key_is_in_progress(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        in_progress = {"error": {"code": "conflict", "message": "busy", "details": {"reason": "idempotency_in_progress"}}}
        route = mock_api.post("/api/v1/jobs").mock(side_effect=[
            httpx.Response(409, json=in_progress),
            httpx.Response(200, json={"data": _job()}),
        ])
        assert _client(api_key, base_url).jobs.run(command="x", gpu_type="A4000", max_runtime_minutes=5).id == JOB_ID
        assert route.call_count == 2
        assert no_sleep[0] >= 3.0

    def test_a_key_reused_with_another_request_is_not_retried(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        conflict = {"error": {"code": "conflict", "message": "differs", "details": {"reason": "idempotency_conflict"}}}
        route = mock_api.post("/api/v1/jobs").mock(return_value=httpx.Response(409, json=conflict))
        with pytest.raises(ConflictError):
            _client(api_key, base_url).jobs.run(command="x", gpu_type="A4000", max_runtime_minutes=5)
        assert route.call_count == 1

    def test_run_refuses_group_fields(self, client: Runcrate) -> None:
        with pytest.raises(TypeError, match="run_group"):
            client.jobs.run(command="x", gpu_type="A4000", max_runtime_minutes=5, count=2)  # type: ignore[call-arg]

    def test_rerun_sends_overrides_with_nulls_and_a_key(self, client: Runcrate, mock_api: respx.MockRouter) -> None:
        route = mock_api.post(f"/api/v1/jobs/{JOB_ID}/rerun").mock(
            return_value=httpx.Response(201, json={"data": _job(rerun_of=JOB_ID)})
        )
        job = client.jobs.rerun(JOB_ID, gpu_count=2, webhook_url=None)
        assert job.rerun_of == JOB_ID
        assert json.loads(route.calls[0].request.content) == {"gpu_count": 2, "webhook_url": None}
        assert len(_key(route.calls[0])) == 36


class TestCreatesTheServerDoesNotDeduplicate:
    """RUN-548: a launch that may have reached the server is never sent a second time."""

    CREATES = {
        "instance": ("/api/v1/instances", lambda c: c.instances.create(name="box", ssh_key_id="k", gpu_type="A4000")),
        "schedule": ("/api/v1/schedules", lambda c: c.schedules.create(
            kind="job", spec={"command": "x", "gpu_type": "A4000", "max_runtime_minutes": 5}, cron="0 2 * * *")),
        "volume": ("/api/v1/storage", lambda c: c.storage.create(name="data", size_gb=10, region="137")),
    }

    @pytest.mark.parametrize("what", list(CREATES))
    def test_sends_an_idempotency_key(self, what: str, client: Runcrate, mock_api: respx.MockRouter) -> None:
        path, create = self.CREATES[what]
        route = mock_api.post(path).mock(return_value=httpx.Response(201, json={"data": {}}))
        try:
            create(client)
        except Exception:
            pass  # the empty answer may not validate; only the request matters here
        assert len(_key(route.calls[0])) == 36

    @pytest.mark.parametrize("what", list(CREATES))
    @pytest.mark.parametrize("error", [httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("closed")])
    def test_not_sent_again_after_a_timeout_or_lost_connection(
        self, what: str, error: Exception, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        path, create = self.CREATES[what]
        route = mock_api.post(path).mock(side_effect=[error, httpx.Response(201, json={"data": {}})])
        with pytest.raises((TimeoutError, ConnectionError)):
            create(_client(api_key, base_url, max_retries=3))
        assert route.call_count == 1

    @pytest.mark.parametrize("status", [500, 502, 504])
    def test_instance_not_sent_again_after_an_ambiguous_server_error(
        self, status: int, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        route = mock_api.post("/api/v1/instances").mock(side_effect=[
            httpx.Response(status, json={"error": {"code": "internal_error", "message": "oops"}}),
            httpx.Response(201, json={"data": {}}),
        ])
        from runcrate import ApiError

        with pytest.raises(ApiError) as exc_info:
            _client(api_key, base_url, max_retries=3).instances.create(name="box", ssh_key_id="k")
        assert exc_info.value.status_code == status
        assert route.call_count == 1

    def test_instance_retried_after_a_503_with_the_same_key(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        instance = {"id": "i1", "name": "box", "status": "creating"}
        route = mock_api.post("/api/v1/instances").mock(side_effect=[
            httpx.Response(503, json={"error": {"code": "service_unavailable", "message": "No GPU"}}, headers={"Retry-After": "1"}),
            httpx.Response(201, json={"data": instance}),
        ])
        assert _client(api_key, base_url).instances.create(name="box", ssh_key_id="k").id == "i1"
        assert _key(route.calls[1]) == _key(route.calls[0])

    def test_instance_retried_when_the_connection_never_opened(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        route = mock_api.post("/api/v1/instances").mock(side_effect=[
            httpx.ConnectError("refused"),
            httpx.Response(201, json={"data": {"id": "i1", "name": "box", "status": "creating"}}),
        ])
        assert _client(api_key, base_url).instances.create(name="box", ssh_key_id="k").id == "i1"
        assert route.call_count == 2

    def test_run_now_not_sent_again_after_a_timeout(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        route = mock_api.post("/api/v1/schedules/s1/run-now").mock(side_effect=[httpx.ReadTimeout("slow")])
        with pytest.raises(TimeoutError):
            _client(api_key, base_url).schedules.run_now("s1")
        assert route.call_count == 1

    def test_reads_still_retried_after_a_lost_connection(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        route = mock_api.get(f"/api/v1/jobs/{JOB_ID}").mock(side_effect=[
            httpx.RemoteProtocolError("closed"),
            httpx.Response(200, json={"data": _job()}),
        ])
        assert _client(api_key, base_url).jobs.get(JOB_ID).id == JOB_ID
        assert route.call_count == 2

    async def test_async_instance_not_sent_again_after_a_timeout(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/instances").mock(side_effect=[httpx.ReadTimeout("slow"), httpx.Response(201, json={"data": {}})])
        client = AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=3)
        with pytest.raises(TimeoutError):
            await client.instances.create(name="box", ssh_key_id="k")
        assert route.call_count == 1
        assert len(_key(route.calls[0])) == 36
        await client.close()

    async def test_async_job_retried_after_a_timeout_with_the_same_key(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/jobs").mock(side_effect=[httpx.ReadTimeout("slow"), httpx.Response(201, json={"data": _job()})])
        client = AsyncRuncrate(api_key=api_key, base_url=base_url, max_retries=1)
        assert (await client.jobs.run(command="x", gpu_type="A4000", max_runtime_minutes=5)).id == JOB_ID
        assert _key(route.calls[1]) == _key(route.calls[0])
        await client.close()


class TestReads:
    def test_list_sends_every_filter_and_repeats_tag(self, client: Runcrate, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/jobs").mock(return_value=httpx.Response(200, json={
            "data": [_job()], "meta": {"cursor": "c2", "hasMore": True},
        }))
        page = client.jobs.list(
            status=["running", "failed"], tags={"team": "ml", "run": "a:b"}, group_id="g1",
            q="train", gpu_type="H100", created_after="2026-10-20T00:00:00Z", limit=50, cursor="c1",
        )
        params = route.calls[0].request.url.params
        assert params["status"] == "running,failed"
        assert params.get_list("tag") == ["team:ml", "run:a:b"]
        assert (params["group_id"], params["q"], params["gpu_type"], params["limit"], params["cursor"]) == ("g1", "train", "H100", "50", "c1")
        assert params["created_after"] == "2026-10-20T00:00:00Z"
        assert page.has_more and page.cursor == "c2"
        assert page.data[0].tags == {"run_id": "r-1"}

    def test_list_all_follows_the_cursor(self, client: Runcrate, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/jobs").mock(side_effect=[
            httpx.Response(200, json={"data": [_job(id="a")], "meta": {"cursor": "c2", "hasMore": True}}),
            httpx.Response(200, json={"data": [_job(id="b")], "meta": {"cursor": None, "hasMore": False}}),
        ])
        assert [j.id for j in client.jobs.list_all(status="succeeded")] == ["a", "b"]
        assert route.calls[1].request.url.params["cursor"] == "c2"

    def test_follow_logs_yields_in_order_until_done(self, client: Runcrate, mock_api: respx.MockRouter) -> None:
        def page(chunks: list[tuple[int, str]], cursor: int, done: bool) -> httpx.Response:
            return httpx.Response(200, json={"data": {
                "job_id": JOB_ID, "status": "succeeded" if done else "running",
                "chunks": [{"seq": s, "ts": "2026-10-21T10:00:00Z", "text": t} for s, t in chunks],
                "cursor": cursor, "truncated": False, "done": done,
            }})

        route = mock_api.get(f"/api/v1/jobs/{JOB_ID}/logs").mock(side_effect=[
            page([(1, "a\n"), (2, "b\n")], 2, False),
            page([(3, "c\n")], 3, True),
        ])
        assert "".join(c.text for c in client.jobs.follow_logs(JOB_ID)) == "a\nb\nc\n"
        assert [c.request.url.params["after"] for c in route.calls] == ["0", "2"]
        assert route.calls[0].request.url.params["follow"] == "true"

    def test_events_of_the_machine_have_no_attempt(self, client: Runcrate, mock_api: respx.MockRouter) -> None:
        mock_api.get(f"/api/v1/jobs/{JOB_ID}/events").mock(return_value=httpx.Response(200, json={"data": [
            {"at": "2026-10-21T14:17:43Z", "kind": "launch_attempt", "detail": "1x A6000", "attempt": 1},
            {"at": "2026-10-21T14:24:37Z", "kind": "machine_up", "detail": None, "attempt": None},
        ]}))
        assert [(e.kind, e.attempt) for e in client.jobs.events(JOB_ID)] == [("launch_attempt", 1), ("machine_up", None)]

    def test_wait_backs_off_until_the_job_ends(
        self, client: Runcrate, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        mock_api.get(f"/api/v1/jobs/{JOB_ID}").mock(side_effect=[
            httpx.Response(200, json={"data": _job(status="queued")}),
            httpx.Response(200, json={"data": _job(status="running")}),
            httpx.Response(200, json={"data": _job(status="running")}),
            httpx.Response(200, json={"data": _job(status="failed", exit_code=3)}),
        ])
        job = client.jobs.wait(JOB_ID, poll_interval=1, max_poll_interval=3)
        assert (job.status, job.exit_code, job.finished) == ("failed", 3, True)
        assert no_sleep == [1, 2, 3]

    def test_wait_times_out_with_the_job_as_last_seen(
        self, client: Runcrate, mock_api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now = [0.0]
        monkeypatch.setattr("runcrate.resources.jobs.time.monotonic", lambda: now[0])
        monkeypatch.setattr("runcrate.resources.jobs.time.sleep", lambda s: now.__setitem__(0, now[0] + s))
        mock_api.get(f"/api/v1/jobs/{JOB_ID}").mock(return_value=httpx.Response(200, json={"data": _job(status="running")}))
        with pytest.raises(JobWaitTimeoutError) as exc_info:
            client.jobs.wait(JOB_ID, timeout=5, poll_interval=2)
        assert exc_info.value.job.status == "running"
        assert now[0] == 5


class TestFiles:
    def test_download_follows_no_redirect_and_sends_no_key_to_the_signed_url(
        self, client: Runcrate, mock_api: respx.MockRouter, tmp_path: Path
    ) -> None:
        artifact = mock_api.get(f"/api/v1/jobs/{JOB_ID}/artifacts/runs/a%20b.txt").mock(
            return_value=httpx.Response(302, headers={"Location": "https://files.example.com/o?sig=1"})
        )
        with respx.mock(assert_all_called=False) as files:
            signed = files.get("https://files.example.com/o?sig=1").mock(return_value=httpx.Response(200, content=b"\x07\x08"))
            assert client.jobs.artifacts.download(JOB_ID, "runs/a b.txt") == b"\x07\x08"
            target = client.jobs.artifacts.download(JOB_ID, "runs/a b.txt", to=tmp_path / "out.bin")
        assert Path(target).read_bytes() == b"\x07\x08"
        assert artifact.call_count == 2
        assert "authorization" not in signed.calls[0].request.headers

    def test_upload_packs_a_directory_without_git_and_skips_a_known_upload(
        self, client: Runcrate, mock_api: respx.MockRouter, tmp_path: Path
    ) -> None:
        (tmp_path / "train.py").write_text("print(1)\n")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref\n")
        create = mock_api.post("/api/v1/jobs/uploads").mock(side_effect=[
            httpx.Response(201, json={"data": {"upload_id": "u1", "url": "https://files.example.com/put", "expires_at": "2026-10-22T10:00:00Z", "max_bytes": 1}}),
            httpx.Response(201, json={"data": {"upload_id": "u1", "url": None, "expires_at": "2026-10-22T10:00:00Z", "max_bytes": 1}}),
        ])
        with respx.mock(assert_all_called=False) as files:
            put = files.put("https://files.example.com/put").mock(return_value=httpx.Response(200))
            assert client.jobs.uploads.upload(tmp_path).upload_id == "u1"
            client.jobs.uploads.upload(tmp_path)
        sent = put.calls[0].request.content
        with tarfile.open(fileobj=io.BytesIO(sent), mode="r:gz") as archive:
            assert archive.getnames() == ["train.py"]
        body = json.loads(create.calls[0].request.content)
        assert body == {"bytes": len(sent), "sha256": hashlib.sha256(sent).hexdigest()}
        assert put.call_count == 1

    def test_packing_the_same_files_twice_makes_the_same_bytes(self, tmp_path: Path) -> None:
        import os
        import time as _time

        from runcrate.resources.jobs import _code_archive

        (tmp_path / "pkg").mkdir()
        (tmp_path / "train.py").write_text("print(1)\n")
        (tmp_path / "train.py").chmod(0o755)
        (tmp_path / "pkg" / "u.py").write_text("x = 1\n")
        first = _code_archive(tmp_path)
        later = _time.time() + 3600
        os.utime(tmp_path / "train.py", (later, later))
        os.utime(tmp_path / "pkg", (later, later))
        _time.sleep(1.1)  # a gzip header with the time in it would differ now
        assert _code_archive(tmp_path) == first
        with tarfile.open(fileobj=io.BytesIO(first), mode="r:gz") as archive:
            members = archive.getmembers()
        assert [(m.name, m.uid, m.uname, m.mtime) for m in members] == [("train.py", 0, "", 0), ("pkg/u.py", 0, "", 0)]
        assert members[0].mode & 0o111

    def test_group_cancel_repeats_after_a_lost_answer(
        self, api_key: str, base_url: str, mock_api: respx.MockRouter, no_sleep: list[float]
    ) -> None:
        route = mock_api.post("/api/v1/job-groups/g1/cancel").mock(side_effect=[
            httpx.RemoteProtocolError("closed"),
            httpx.Response(200, json={"data": {"id": "g1", "count": 2, "max_parallel": 2, "status_counts": {"cancelled": 2}, "created_at": "2026-10-21T10:00:00Z"}}),
        ])
        assert _client(api_key, base_url).job_groups.cancel("g1").status_counts == {"cancelled": 2}
        assert route.call_count == 2
