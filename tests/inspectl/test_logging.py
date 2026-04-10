from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from inspectl.logging import RunSession, StepContext
from inspectl.models import PipelineState


@dataclass
class ExampleState(PipelineState):
    build_id: str | None = None


def test_run_session_writes_jsonl_and_snapshot(tmp_path) -> None:
    session = RunSession(run_id="run-001", root_dir=tmp_path)
    session.record(level="INFO", event="run.start", message="starting")
    session.snapshot(
        step_name="submit_compilation",
        state=ExampleState(run_id="run-001", build_id="build-123"),
    )
    session.close()

    entries = [
        json.loads(line)
        for line in (tmp_path / "run-001" / "session.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    snapshot = json.loads(
        (tmp_path / "run-001" / "state_snapshots" / "001_submit_compilation.json").read_text(
            encoding="utf-8"
        )
    )

    assert entries[0]["event"] == "run.start"
    assert snapshot["build_id"] == "build-123"


def test_step_context_scopes_user_logs(tmp_path) -> None:
    session = RunSession(run_id="run-002", root_dir=tmp_path)
    ctx = StepContext(
        run_id="run-002",
        step_name="submit_compilation",
        attempt=2,
        session=session,
    )

    ctx.info("submitted", build_id="build-456")
    session.close()

    payload = json.loads(
        (tmp_path / "run-002" / "session.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert payload["event"] == "user.info"
    assert payload["step"] == "submit_compilation"
    assert payload["attempt"] == 2
    assert payload["data"]["build_id"] == "build-456"


def test_run_session_record_is_best_effort_for_unserializable_data(tmp_path) -> None:
    session = RunSession(run_id="run-003", root_dir=tmp_path)

    session.record(level="INFO", event="run.start", message="starting", data={"payload": object()})
    session.close()

    assert (tmp_path / "run-003" / "session.jsonl").read_text(encoding="utf-8") == ""


def test_run_session_snapshot_numbers_increment_safely(tmp_path) -> None:
    session = RunSession(run_id="run-004", root_dir=tmp_path)

    first = session.snapshot(
        step_name="submit_compilation",
        state=ExampleState(run_id="run-004", build_id="build-123"),
    )
    second = session.snapshot(
        step_name="sync_code",
        state=ExampleState(run_id="run-004", build_id="build-456"),
    )
    session.close()

    assert first.name == "001_submit_compilation.json"
    assert second.name == "002_sync_code.json"


def test_run_session_reopen_seeds_snapshot_counter(tmp_path) -> None:
    first_session = RunSession(run_id="run-006", root_dir=tmp_path)
    first_snapshot = first_session.snapshot(
        step_name="submit_compilation",
        state=ExampleState(run_id="run-006", build_id="build-123"),
    )
    first_session.close()

    second_session = RunSession(run_id="run-006", root_dir=tmp_path)
    second_snapshot = second_session.snapshot(
        step_name="sync_code",
        state=ExampleState(run_id="run-006", build_id="build-456"),
    )
    second_session.close()

    assert first_snapshot.name == "001_submit_compilation.json"
    assert second_snapshot.name == "002_sync_code.json"


def test_run_session_init_is_best_effort_when_filesystem_setup_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_mkdir(self: Path, *args, **kwargs) -> None:
        raise OSError("boom")

    monkeypatch.setattr("inspectl.logging.Path.mkdir", fail_mkdir)

    session = RunSession(run_id="run-005", root_dir=tmp_path)

    session.record(level="INFO", event="run.start", message="starting")
    session.snapshot(step_name="submit_compilation", state=ExampleState(run_id="run-005"))
    session.close()

    assert not (tmp_path / "run-005").exists()
