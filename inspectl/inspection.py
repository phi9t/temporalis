from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from temporalio.client import Client

from inspectl.local_server import LocalServerManager
from inspectl.models import RuntimeConfig
from inspectl.workflow_runtime import InspectlPipelineWorkflow


def _config(config: RuntimeConfig | None) -> RuntimeConfig:
    return config or RuntimeConfig()


def _run_dir(config: RuntimeConfig, run_id: str) -> Path:
    return Path(config.log_dir) / run_id


def _session_file(config: RuntimeConfig, run_id: str) -> Path:
    return _run_dir(config, run_id) / "session.jsonl"


def _snapshot_dir(config: RuntimeConfig, run_id: str) -> Path:
    return _run_dir(config, run_id) / "state_snapshots"


def _parse_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def _latest_snapshot_name(config: RuntimeConfig, run_id: str) -> str | None:
    snapshots = _snapshot_dir(config, run_id)
    if not snapshots.exists():
        return None

    candidates = sorted(path for path in snapshots.glob("*.json") if path.is_file())
    if not candidates:
        return None
    return candidates[-1].name


def _expected_task_queue(config: RuntimeConfig, pipeline: str) -> str:
    return f"{config.task_queue_prefix}-{pipeline}"


def _summarize_logs(run_id: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "run_id": run_id,
        "status": "unknown",
        "pipeline": None,
        "task_queue": None,
        "failure_step": None,
        "failure_reason": None,
        "updated_at": None,
        "state": None,
        "log_count": len(entries),
    }

    for entry in entries:
        timestamp = entry.get("timestamp")
        if isinstance(timestamp, str):
            summary["updated_at"] = timestamp

        event = entry.get("event")
        data = entry.get("data")
        if event == "run.start" and isinstance(data, dict):
            pipeline = data.get("pipeline")
            if isinstance(pipeline, str):
                summary["pipeline"] = pipeline
            if isinstance(data.get("resume"), bool):
                summary["resume"] = data["resume"]
            summary["status"] = "running"
        elif event == "run.paused":
            summary["status"] = "paused"
            if isinstance(entry.get("message"), str):
                summary["failure_reason"] = entry["message"]
        elif event == "run.complete":
            summary["status"] = "completed"

        if isinstance(data, dict):
            failure_step = data.get("failure_step")
            failure_reason = data.get("failure_reason")
            if isinstance(failure_step, str):
                summary["failure_step"] = failure_step
            if isinstance(failure_reason, str):
                summary["failure_reason"] = failure_reason

    if summary["updated_at"] is None and entries:
        summary["updated_at"] = entries[-1].get("timestamp")

    return summary


async def _connect_with_retries(
    *,
    target: str,
    namespace: str,
    ownership_check,
) -> Client:
    last_error: Exception | None = None
    for _ in range(25):
        if not ownership_check():
            raise RuntimeError(
                "inspectl local Temporal server is not owned by this workspace or is no longer running"
            )
        try:
            return await Client.connect(target, namespace=namespace)
        except Exception as exc:  # pragma: no cover - temporal connection failures are environment-specific
            last_error = exc
            await asyncio.sleep(0.2)

    assert last_error is not None
    raise last_error


async def _runtime_client(config: RuntimeConfig) -> Client | None:
    manager = LocalServerManager(config)
    state = manager.read_state()
    if not manager.is_runtime_state_valid(state):
        return None

    assert state is not None
    return await _connect_with_retries(
        target=state["target"],
        namespace=config.namespace,
        ownership_check=lambda: manager.is_runtime_state_valid(state),
    )


async def _workflow_details(client: Client, run_id: str) -> dict[str, Any]:
    handle = client.get_workflow_handle(run_id)

    describe: Any | None = None
    try:
        describe = await handle.describe()
    except Exception:
        pass

    query: Any | None = None
    try:
        query = await handle.query(InspectlPipelineWorkflow.describe)
    except Exception:
        pass

    details: dict[str, Any] = {}
    if describe is not None:
        task_queue = getattr(describe, "task_queue", None)
        if isinstance(task_queue, str):
            details["task_queue"] = task_queue
        status = getattr(describe, "status", None)
        if status is not None:
            details["workflow_status"] = getattr(status, "value", str(status))

    if isinstance(query, dict):
        for key in ("status", "failure_step", "failure_reason", "state"):
            value = query.get(key)
            if value is not None:
                details[key] = value

    return details


def _workflow_task_queue(description: Any) -> str | None:
    task_queue = getattr(description, "task_queue", None)
    return task_queue if isinstance(task_queue, str) else None


async def _inspect_run(
    run_id: str,
    config: RuntimeConfig,
    *,
    client: Client | None,
) -> dict[str, Any]:
    entries = _parse_json_lines(_session_file(config, run_id))
    if not entries:
        raise RuntimeError(f"run '{run_id}' has no local session log")

    summary = _summarize_logs(run_id, entries)
    summary["latest_snapshot"] = _latest_snapshot_name(config, run_id)

    if client is not None:
        details = await _workflow_details(client, run_id)
        workflow_status = details.get("workflow_status")
        if isinstance(workflow_status, str):
            summary["workflow_status"] = workflow_status
        for key in ("status", "task_queue", "failure_step", "failure_reason", "state"):
            value = details.get(key)
            if value is not None:
                summary[key] = value

    return summary


async def list_runs(config: RuntimeConfig | None = None) -> list[dict[str, Any]]:
    config = _config(config)
    client = await _runtime_client(config)

    log_root = Path(config.log_dir)
    if not log_root.exists():
        return []

    run_dirs = [path for path in log_root.iterdir() if path.is_dir()]
    summaries: list[dict[str, Any]] = []
    for run_dir in sorted(run_dirs, key=lambda path: path.name):
        try:
            summary = await _inspect_run(run_dir.name, config, client=client)
        except RuntimeError:
            continue
        summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            item.get("updated_at") is None,
            item.get("updated_at") or "",
            item.get("run_id") or "",
        ),
        reverse=True,
    )
    return summaries


async def inspect_run(
    run_id: str, config: RuntimeConfig | None = None
) -> dict[str, Any]:
    config = _config(config)
    client = await _runtime_client(config)
    return await _inspect_run(run_id, config, client=client)


async def read_run_logs(
    run_id: str, config: RuntimeConfig | None = None
) -> list[dict[str, Any]]:
    config = _config(config)
    session_file = _session_file(config, run_id)
    if not session_file.exists():
        raise RuntimeError(f"run '{run_id}' has no local session log")

    try:
        return _parse_json_lines(session_file)
    except OSError as exc:
        raise RuntimeError(f"run '{run_id}' session log is unreadable") from exc


async def resume_run(
    run_id: str, config: RuntimeConfig | None = None
) -> dict[str, Any]:
    config = _config(config)
    local_summary = await _inspect_run(run_id, config, client=None)
    pipeline = local_summary.get("pipeline")
    if not isinstance(pipeline, str) or not pipeline:
        raise RuntimeError(f"run '{run_id}' is missing pipeline metadata in its local session log")

    expected_task_queue = _expected_task_queue(config, pipeline)
    client = await _runtime_client(config)
    if client is None:
        raise RuntimeError("inspectl local Temporal server is not running")

    handle = client.get_workflow_handle(run_id)
    description = await handle.describe()
    task_queue = _workflow_task_queue(description)
    if task_queue != expected_task_queue:
        raise RuntimeError(
            f"run_id '{run_id}' belongs to a different pipeline "
            f"(expected task queue '{expected_task_queue}', found '{task_queue}')"
        )

    await handle.signal(InspectlPipelineWorkflow.resume)
    return await _inspect_run(run_id, config, client=client)
