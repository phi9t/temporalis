from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from inspectl.models import RuntimeConfig
from inspectl.inspection import resume_run
from inspectl.runtime import run as runtime_run


def test_inspectl_package_exports_run() -> None:
    from inspectl import run

    assert run is runtime_run


@dataclass
class _FakeDescription:
    task_queue: str


class _FakeHandle:
    def __init__(self, task_queue: str) -> None:
        self.task_queue = task_queue
        self.signal_called = False

    async def describe(self) -> _FakeDescription:
        return _FakeDescription(task_queue=self.task_queue)

    async def signal(self, _signal) -> None:
        self.signal_called = True


class _FakeClient:
    def __init__(self, handle: _FakeHandle) -> None:
        self.handle = handle

    def get_workflow_handle(self, _run_id: str) -> _FakeHandle:
        return self.handle


@pytest.mark.asyncio
async def test_resume_run_fails_without_local_session_before_temporal_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl", log_dir=tmp_path / "runs")
    called = False

    async def fake_runtime_client(_config: RuntimeConfig):
        nonlocal called
        called = True
        raise AssertionError("runtime client should not be requested")

    monkeypatch.setattr("inspectl.inspection._runtime_client", fake_runtime_client)

    with pytest.raises(RuntimeError, match="no local session log"):
        await resume_run("run-missing", config)

    assert called is False


@pytest.mark.asyncio
async def test_resume_run_rejects_task_queue_mismatch_before_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run-001"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("session.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-10T12:00:00Z",
                        "run_id": "run-001",
                        "level": "INFO",
                        "event": "run.start",
                        "message": "starting inspectl pipeline runtime",
                        "data": {"pipeline": "demo-pipeline", "resume": False},
                    }
                )
            ]
        ),
        encoding="utf-8",
    )

    handle = _FakeHandle(task_queue="inspectl-other-pipeline")
    client = _FakeClient(handle)
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl", log_dir=runs_dir)

    async def fake_runtime_client(_config: RuntimeConfig) -> _FakeClient:
        return client

    monkeypatch.setattr("inspectl.inspection._runtime_client", fake_runtime_client)

    with pytest.raises(RuntimeError, match="different pipeline"):
        await resume_run("run-001", config)

    assert handle.signal_called is False


def test_inspectl_cli_list(monkeypatch, capsys) -> None:
    async def fake_list_runs(config) -> list[dict[str, str]]:
        assert config.namespace == "default"
        return [
            {
                "run_id": "run-001",
                "status": "paused",
                "pipeline": "demo-pipeline",
                "updated_at": "2026-04-10T12:01:00Z",
            },
            {
                "run_id": "run-002",
                "status": "completed",
                "pipeline": "other-pipeline",
                "updated_at": "2026-04-10T12:02:00Z",
            },
        ]

    monkeypatch.setattr("inspectl.cli.list_runs", fake_list_runs)

    from inspectl.cli import run

    assert run(["list"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "run_id\tstatus\tpipeline\tupdated_at",
        "run-001\tpaused\tdemo-pipeline\t2026-04-10T12:01:00Z",
        "run-002\tcompleted\tother-pipeline\t2026-04-10T12:02:00Z",
    ]


def test_inspectl_cli_inspect(monkeypatch, capsys) -> None:
    async def fake_inspect_run(run_id: str, config) -> dict[str, str | None]:
        assert run_id == "run-001"
        assert config.log_dir.name == "runs"
        return {
            "run_id": "run-001",
            "status": "paused",
            "pipeline": "demo-pipeline",
            "task_queue": "inspectl-demo-pipeline",
            "failure_step": "submit_compilation",
            "failure_reason": "waiting on input",
            "updated_at": "2026-04-10T12:01:00Z",
            "latest_snapshot": "002_finalize_build.json",
        }

    monkeypatch.setattr("inspectl.cli.inspect_run", fake_inspect_run)

    from inspectl.cli import run

    assert run(["inspect", "run-001"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "run_id: run-001",
        "status: paused",
        "pipeline: demo-pipeline",
        "task_queue: inspectl-demo-pipeline",
        "failure_step: submit_compilation",
        "failure_reason: waiting on input",
        "updated_at: 2026-04-10T12:01:00Z",
        "latest_snapshot: 002_finalize_build.json",
    ]


def test_inspectl_cli_logs(monkeypatch, capsys) -> None:
    async def fake_read_run_logs(run_id: str, config) -> Sequence[dict[str, object]]:
        assert run_id == "run-001"
        assert config.local_state_dir.name == ".inspectl"
        return [
            {
                "timestamp": "2026-04-10T12:00:00Z",
                "level": "INFO",
                "event": "run.start",
                "message": "starting inspectl pipeline runtime",
            },
            {
                "timestamp": "2026-04-10T12:01:00Z",
                "level": "ERROR",
                "event": "run.paused",
                "message": "workflow paused awaiting resume",
            },
        ]

    monkeypatch.setattr("inspectl.cli.read_run_logs", fake_read_run_logs)

    from inspectl.cli import run

    assert run(["logs", "run-001"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "2026-04-10T12:00:00Z INFO run.start starting inspectl pipeline runtime",
        "2026-04-10T12:01:00Z ERROR run.paused workflow paused awaiting resume",
    ]


def test_inspectl_cli_logs_missing_session_fails(tmp_path: Path, capsys) -> None:
    from inspectl.cli import run

    assert run(["--log-dir", str(tmp_path / "runs"), "logs", "run-missing"]) == 1

    assert capsys.readouterr().err.strip() == "run 'run-missing' has no local session log"


def test_inspectl_cli_resume(monkeypatch, capsys) -> None:
    async def fake_resume_run(run_id: str, config) -> dict[str, str]:
        assert run_id == "run-001"
        assert config.port == 7233
        return {"run_id": "run-001", "status": "running"}

    monkeypatch.setattr("inspectl.cli.resume_run", fake_resume_run)

    from inspectl.cli import run

    assert run(["resume", "run-001"]) == 0

    assert capsys.readouterr().out.splitlines() == ["run-001: running"]
