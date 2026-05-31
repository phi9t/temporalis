#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from _refs import github_url, load_repos, repo_abs_path, resolve_line


def ref(
    repo_root: Path,
    repos,
    repo_id: str,
    path: str,
    symbol: str,
    label: str,
    *,
    pattern: str | None = None,
) -> dict[str, Any]:
    repo = repos[repo_id]
    return {
        "repo": repo_id,
        "label": label,
        "path": path,
        "line": resolve_line(repo_abs_path(repo_root, repo), path, symbol, pattern=pattern),
        "symbol": symbol,
        "url": f"{github_url(repo.remote)}/blob/{repo.head}/{path}",
    }


def local_head(repo_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def local_ref(
    repo_root: Path,
    path: str,
    symbol: str,
    label: str,
    *,
    pattern: str | None = None,
) -> dict[str, Any]:
    return {
        "repo": "kilvin",
        "label": label,
        "path": path,
        "line": resolve_line(repo_root, path, symbol, pattern=pattern),
        "symbol": symbol,
        "url": f"https://github.com/phi9t/temporalis/blob/{local_head(repo_root)}/{path}",
    }


def edge(edge_id: str, source: str, target: str, kind: str, label: str) -> dict[str, str]:
    return {"id": edge_id, "from": source, "to": target, "kind": kind, "label": label}


def lock_generated_at(repo_root: Path) -> str:
    raw = json.loads((repo_root / ".monorepo" / "current.lock.json").read_text(encoding="utf-8"))
    return raw["generated_at"]


def build(repo_root: Path) -> dict[str, Any]:
    repos = load_repos(repo_root)
    nodes = [
        {
            "id": "kilvin-client",
            "label": "Kilvin client",
            "layer": "kilvin",
            "kind": "client",
            "summary": "Starts the parent command workflow with a staged training config.",
            "notes": "The sample config models foundation and post-foundation stages, which gives the walkthrough enough complexity to explain task queues, child workflows, activities, retries, and cleanup.",
            "refs": [
                local_ref(
                    repo_root,
                    "kilvin-py/start_workflow.py",
                    "await client.execute_workflow(",
                    "start_workflow.py",
                    pattern=r"^\s*\w+\s*=\s*await client\.execute_workflow\(",
                )
            ],
        },
        {
            "id": "python-worker",
            "label": "Python Worker.run",
            "layer": "sdk-python",
            "kind": "worker",
            "summary": "Runs asyncio poll loops for workflow activations and activity tasks.",
            "notes": "Python owns user-code execution and asyncio scheduling; sdk-core owns task polling, workflow cache, state machines, and server completions.",
            "refs": [
                local_ref(repo_root, "kilvin-py/worker.py", "Worker(", "kilvin worker"),
                ref(repo_root, repos, "sdk-python", "temporalio/worker/_worker.py", "class Worker", "sdk-python Worker", pattern=r"^class Worker:"),
                ref(repo_root, repos, "sdk-python", "temporalio/worker/_workflow.py", "async def run", "workflow poll loop", pattern=r"^\s+async def run\("),
                ref(repo_root, repos, "sdk-python", "temporalio/worker/_activity.py", "async def run", "activity poll loop", pattern=r"^\s+async def run\("),
            ],
        },
        {
            "id": "bridge-worker",
            "label": "Bridge worker",
            "layer": "bridge",
            "kind": "bridge",
            "summary": "Serializes Python async calls into sdk-core worker operations.",
            "notes": "The Python bridge exposes poll_workflow_activation, poll_activity_task, completion, and heartbeat calls backed by the Rust C bridge.",
            "refs": [
                ref(repo_root, repos, "sdk-python", "temporalio/bridge/worker.py", "poll_workflow_activation", "Python bridge poll activation", pattern=r"^\s+async def poll_workflow_activation\("),
                ref(repo_root, repos, "sdk-python", "temporalio/bridge/worker.py", "complete_workflow_activation", "Python bridge complete activation", pattern=r"^\s+async def complete_workflow_activation\("),
                ref(repo_root, repos, "sdk-core", "crates/sdk-core-c-bridge/src/worker.rs", "temporal_core_worker_poll_workflow_activation", "C bridge poll activation", pattern=r"^pub extern \"C\" fn temporal_core_worker_poll_workflow_activation\("),
            ],
        },
        {
            "id": "core-runtime",
            "label": "Core runtime",
            "layer": "sdk-core",
            "kind": "runtime",
            "summary": "Hosts the Tokio runtime, telemetry, heartbeat interval, and worker initialization.",
            "notes": "CoreRuntime is created before workers or clients call async core functions so tracing and runtime state are attached correctly.",
            "refs": [ref(repo_root, repos, "sdk-core", "crates/sdk-core/src/lib.rs", "pub struct CoreRuntime", "CoreRuntime", pattern=r"^pub struct CoreRuntime \{")],
        },
        {
            "id": "core-worker",
            "label": "Core worker",
            "layer": "sdk-core",
            "kind": "worker",
            "summary": "Manages pollers, slots, sticky cache, workflow activations, activity tasks, and completions.",
            "notes": "Core converts server workflow-task responses into activations for Python and converts Python completions back into Temporal commands.",
            "refs": [
                ref(repo_root, repos, "sdk-core", "crates/sdk-core/src/lib.rs", "pub fn init_worker", "init_worker", pattern=r"^pub fn init_worker\("),
                ref(repo_root, repos, "sdk-core", "crates/sdk-core/src/worker/mod.rs", "pub struct WorkerConfig", "WorkerConfig", pattern=r"^pub struct WorkerConfig \{"),
            ],
        },
        {
            "id": "frontend-service",
            "label": "Frontend",
            "layer": "server",
            "kind": "service",
            "summary": "Accepts client RPCs such as starting workflows and completing tasks.",
            "notes": "Frontend is the public gRPC entrypoint and routes workflow operations into History and task polling behavior.",
            "refs": [
                ref(
                    repo_root,
                    repos,
                    "temporal",
                    "service/frontend/workflow_handler.go",
                    "StartWorkflowExecution",
                    "StartWorkflowExecution",
                    pattern=r"^func \(.*\) StartWorkflowExecution\(",
                )
            ],
        },
        {
            "id": "history-service",
            "label": "History",
            "layer": "server",
            "kind": "history",
            "summary": "Owns durable workflow history and turns commands into new events and tasks.",
            "notes": "History is the source of truth for replay. Workflow progress is event-sourced, not stored in Python process memory.",
            "refs": [
                ref(
                    repo_root,
                    repos,
                    "temporal",
                    "service/history/handler.go",
                    "RespondWorkflowTaskCompleted",
                    "RespondWorkflowTaskCompleted",
                    pattern=r"^func \(.*\) RespondWorkflowTaskCompleted\(",
                )
            ],
        },
        {
            "id": "matching-service",
            "label": "Matching",
            "layer": "server",
            "kind": "task-queue",
            "summary": "Matches workflow and activity tasks to polling workers on task queues.",
            "notes": "Matching is why workers poll instead of the server directly invoking user processes.",
            "refs": [
                ref(
                    repo_root,
                    repos,
                    "temporal",
                    "service/matching/handler.go",
                    "PollWorkflowTaskQueue",
                    "PollWorkflowTaskQueue",
                    pattern=r"^func \(.*\) PollWorkflowTaskQueue\(",
                )
            ],
        },
        {
            "id": "workflow-activation",
            "label": "Activation",
            "layer": "sdk-python",
            "kind": "workflow",
            "summary": "Python receives a WorkflowActivation and resumes deterministic workflow code.",
            "notes": "For the Kilvin-inspired flow, activation drives the parent workflow and child training workflow until they block on commands.",
            "refs": [
                ref(
                    repo_root,
                    repos,
                    "sdk-python",
                    "temporalio/worker/_workflow.py",
                    "_handle_activation",
                    "_handle_activation",
                    pattern=r"^\s+async def _handle_activation\(",
                )
            ],
        },
        {
            "id": "activity-task",
            "label": "Activity task",
            "layer": "sdk-python",
            "kind": "activity",
            "summary": "Python executes async activities such as resource allocation, bundle materialization, and monitoring.",
            "notes": "Activities perform side effects and heartbeat progress while workflow code remains deterministic.",
            "refs": [
                local_ref(repo_root, "kilvin-py/kilvin_py/activities.py", "async def allocate_resources", "allocate_resources", pattern=r"^async def allocate_resources\("),
                local_ref(repo_root, "kilvin-py/kilvin_py/activities.py", "async def monitor_training", "monitor_training", pattern=r"^async def monitor_training\("),
            ],
        },
    ]
    edges = [
        edge("start-rpc", "kilvin-client", "frontend-service", "rpc", "StartWorkflowExecution"),
        edge("history-start", "frontend-service", "history-service", "history-event", "append WorkflowExecutionStarted"),
        edge("schedule-wft", "history-service", "matching-service", "task-dispatch", "enqueue workflow task"),
        edge("worker-poll", "python-worker", "bridge-worker", "poll", "await poll_workflow_activation"),
        edge("bridge-core", "bridge-worker", "core-worker", "poll", "core poller"),
        edge("core-matching", "core-worker", "matching-service", "poll", "PollWorkflowTaskQueue"),
        edge("activation-up", "core-worker", "workflow-activation", "activation", "WorkflowActivation"),
        edge("activity-command", "workflow-activation", "history-service", "command", "ScheduleActivityTask command"),
        edge("activity-dispatch", "history-service", "matching-service", "task-dispatch", "enqueue activity task"),
        edge("activity-poll", "core-worker", "activity-task", "activation", "ActivityTask"),
        edge("heartbeat", "activity-task", "core-worker", "heartbeat", "RecordHeartbeat"),
        edge("activity-complete", "activity-task", "history-service", "completion", "ActivityTaskCompleted"),
        edge("workflow-complete", "workflow-activation", "history-service", "completion", "RespondWorkflowTaskCompleted"),
    ]
    phases = [
        {"id": "start", "label": "Start workflow", "summary": "Kilvin submits a staged training run.", "node_ids": ["kilvin-client", "frontend-service", "history-service"]},
        {"id": "poll", "label": "Poll task queue", "summary": "Worker polling crosses Python, bridge, core, and Matching.", "node_ids": ["python-worker", "bridge-worker", "core-worker", "matching-service"]},
        {"id": "activate", "label": "Activate workflow", "summary": "Core delivers a workflow activation to Python asyncio code.", "node_ids": ["core-worker", "workflow-activation", "python-worker"]},
        {"id": "schedule-activity", "label": "Schedule activity", "summary": "Workflow commands become durable history events and activity tasks.", "node_ids": ["workflow-activation", "history-service", "matching-service"]},
        {"id": "execute-activity", "label": "Execute activity", "summary": "Python runs side-effecting activity code and heartbeats progress.", "node_ids": ["activity-task", "core-worker", "history-service"]},
        {"id": "complete", "label": "Complete turn", "summary": "Completions update history and may schedule the next workflow task.", "node_ids": ["workflow-activation", "history-service", "matching-service"]},
    ]
    return {
        "generated_at": lock_generated_at(repo_root),
        "slug": "kilvin-asyncio-happy-path",
        "label": "Kilvin asyncio happy path",
        "phases": phases,
        "nodes": nodes,
        "edges": edges,
    }


def control_scenarios() -> list[dict[str, Any]]:
    return [
        {"slug": "pause-resume", "label": "Pause / resume", "summary": "Signals change workflow state; replay preserves deterministic history.", "highlight_node_ids": ["workflow-activation", "history-service"], "highlight_edge_ids": ["workflow-complete", "schedule-wft"]},
        {"slug": "retry", "label": "Retry", "summary": "Activity failure appends history and server/core coordinate retry dispatch.", "highlight_node_ids": ["activity-task", "history-service", "matching-service"], "highlight_edge_ids": ["activity-complete", "activity-dispatch"]},
        {"slug": "replay", "label": "Replay", "summary": "History events rebuild workflow state before new commands are accepted.", "highlight_node_ids": ["history-service", "core-worker", "workflow-activation"], "highlight_edge_ids": ["activation-up", "workflow-complete"]},
        {"slug": "heartbeat-cancellation", "label": "Heartbeat cancellation", "summary": "Activity heartbeats let cancellation and progress flow through core.", "highlight_node_ids": ["activity-task", "core-worker", "history-service"], "highlight_edge_ids": ["heartbeat", "activity-complete"]},
        {"slug": "sticky-cache-eviction", "label": "Sticky cache eviction", "summary": "Core cache eviction moves execution back to replay from history.", "highlight_node_ids": ["core-worker", "history-service", "matching-service"], "highlight_edge_ids": ["core-matching", "activation-up"]},
    ]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    out = repo_root / "explorer" / "public" / "data"

    lifecycle = build(repo_root)
    write_json(out / "lifecycle" / "kilvin-asyncio-happy-path.json", lifecycle)
    write_json(
        out / "lifecycle" / "index.json",
        [{"slug": lifecycle["slug"], "label": lifecycle["label"], "manifest": "lifecycle/kilvin-asyncio-happy-path.json"}],
    )

    scenarios = control_scenarios()
    write_json(
        out / "control-paths" / "index.json",
        [{"slug": s["slug"], "label": s["label"], "manifest": f"control-paths/{s['slug']}.json"} for s in scenarios],
    )
    for scenario in scenarios:
        write_json(out / "control-paths" / f"{scenario['slug']}.json", scenario)

    repos = load_repos(repo_root)
    write_json(
        out / "repos.json",
        {
            repo_id: {"branch": repo.branch, "head": repo.head, "remote": repo.remote, "github": github_url(repo.remote)}
            for repo_id, repo in sorted(repos.items())
        },
    )
    print("wrote lifecycle and control-path manifests")


if __name__ == "__main__":
    main()
