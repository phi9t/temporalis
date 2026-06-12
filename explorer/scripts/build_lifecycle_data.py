#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

from _refs import RepoInfo, github_url, load_repos, repo_abs_path, resolve_line


def _worktree_main_root(repo_root: Path) -> Path | None:
    git_file = repo_root / ".git"
    if not git_file.is_file():
        return None
    content = git_file.read_text(encoding="utf-8").strip()
    if not content.startswith("gitdir: "):
        return None
    git_dir = Path(content.removeprefix("gitdir: "))
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()
    try:
        common_git = git_dir.parents[1]
    except IndexError:
        return None
    return common_git.parent if common_git.name == ".git" else None


def source_repo_abs_path(repo_root: Path, repo: RepoInfo) -> Path:
    main_root = _worktree_main_root(repo_root)
    candidates = [
        repo_abs_path(repo_root, repo),
        repo_root / Path(repo.path).name,
    ]
    if main_root is not None:
        candidates.extend(
            [
                main_root / repo.path,
                main_root / Path(repo.path).name,
                main_root / ".monorepo" / repo.path,
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


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
        "line": resolve_line(source_repo_abs_path(repo_root, repo), path, symbol, pattern=pattern),
        "symbol": symbol,
        "url": f"{github_url(repo.remote)}/blob/{repo.head}/{path}",
    }


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
        "ref": "phi9t-mainline",
        "label": label,
        "path": path,
        "line": resolve_line(repo_root, path, symbol, pattern=pattern),
        "symbol": symbol,
        "url": f"https://github.com/phi9t/temporalis/blob/phi9t-mainline/{path}",
    }


def edge(edge_id: str, source: str, target: str, kind: str, label: str) -> dict[str, str]:
    return {"id": edge_id, "from": source, "to": target, "kind": kind, "label": label}


def call(
    call_id: str,
    phase_id: str,
    seq: int,
    source: str,
    target: str,
    edge_id: str,
    kind: str,
    message: str,
    summary: str,
    details: list[str],
    payload: list[str],
    refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": call_id,
        "phase_id": phase_id,
        "seq": seq,
        "from": source,
        "to": target,
        "edge_id": edge_id,
        "kind": kind,
        "message": message,
        "summary": summary,
        "details": details,
        "payload": payload,
        "refs": refs or [],
    }


def control_step(
    step_id: str,
    seq: int,
    kind: str,
    message: str,
    summary: str,
    details: list[str],
    *,
    source: str | None = None,
    target: str | None = None,
    edge_id: str | None = None,
    affected_node_ids: list[str] | None = None,
    affected_edge_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "seq": seq,
        "kind": kind,
        "from": source,
        "to": target,
        "edge_id": edge_id,
        "message": message,
        "summary": summary,
        "details": details,
        "affected_node_ids": affected_node_ids or [],
        "affected_edge_ids": affected_edge_ids or [],
    }


def lock_generated_at(repo_root: Path) -> str:
    raw = json.loads((repo_root / ".monorepo" / "current.lock.json").read_text(encoding="utf-8"))
    return raw["generated_at"]


def guide_sections(repo_root: Path) -> dict[str, str]:
    path = repo_root / "HACKERS_GUIDE.md"
    sections: dict[str, str] = {}
    pending_anchor: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        anchor_match = re.fullmatch(r'<a\s+id="([^"]+)"></a>', line.strip())
        if anchor_match:
            pending_anchor = anchor_match.group(1)
            continue
        if not line.startswith("## "):
            continue
        if pending_anchor is None:
            raise ValueError(f"guide heading {line!r} is missing an explicit anchor")
        title = line.removeprefix("## ").strip()
        if pending_anchor in sections:
            raise ValueError(f"duplicate guide anchor {pending_anchor!r}")
        sections[pending_anchor] = title
        pending_anchor = None
    if pending_anchor is not None:
        raise ValueError(f"guide anchor {pending_anchor!r} is not attached to a section heading")
    return sections


def _string_constant(path: Path, name: str, value: ast.expr) -> str:
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        raise ValueError(f"{path.relative_to(path.parents[1])}: {name} must be a string")
    return value.value


def _string_tuple_constant(path: Path, name: str, value: ast.expr) -> tuple[str, ...]:
    if not isinstance(value, ast.Tuple):
        raise ValueError(f"{path.relative_to(path.parents[1])}: {name} must be a tuple of strings")
    anchors: list[str] = []
    for item in value.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            raise ValueError(f"{path.relative_to(path.parents[1])}: {name} must contain only strings")
        anchors.append(item.value)
    if not anchors:
        raise ValueError(f"{path.relative_to(path.parents[1])}: {name} must not be empty")
    return tuple(anchors)


def read_hack_metadata(repo_root: Path) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for path in sorted((repo_root / "hacks").glob("[0-9][0-9][0-9]_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        values: dict[str, str | tuple[str, ...]] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name not in {"GUIDE_ANCHOR", "GUIDE_ANCHORS", "SUMMARY"}:
                continue
            if name == "GUIDE_ANCHORS":
                values[name] = _string_tuple_constant(path, name, node.value)
            else:
                values[name] = _string_constant(path, name, node.value)

        for required in ("GUIDE_ANCHOR", "SUMMARY"):
            if required not in values:
                raise ValueError(f"hacks/{path.name}: missing {required}")

        guide_anchor = values["GUIDE_ANCHOR"]
        hack_summary = values["SUMMARY"]
        if not isinstance(guide_anchor, str):
            raise ValueError(f"hacks/{path.name}: GUIDE_ANCHOR must be a string")
        if not isinstance(hack_summary, str):
            raise ValueError(f"hacks/{path.name}: SUMMARY must be a string")
        guide_anchors = values.get("GUIDE_ANCHORS", (guide_anchor,))
        if not isinstance(guide_anchors, tuple):
            raise ValueError(f"hacks/{path.name}: GUIDE_ANCHORS must be a tuple of strings")
        if guide_anchor not in guide_anchors:
            raise ValueError(f"hacks/{path.name}: GUIDE_ANCHORS must include GUIDE_ANCHOR {guide_anchor!r}")

        metadata[f"hacks/{path.name}"] = {
            "guide_anchor": guide_anchor,
            "guide_anchors": list(guide_anchors),
            "hack_summary": hack_summary,
        }
    return metadata


def validate_hack_guide_anchors(guide: dict[str, str], hacks: dict[str, dict[str, Any]]) -> None:
    for script, metadata in sorted(hacks.items()):
        anchors = [metadata["guide_anchor"], *metadata["guide_anchors"]]
        for anchor in anchors:
            if anchor not in guide:
                raise ValueError(f"{script} advertises unsupported guide anchor {anchor!r}")


def guide_link(repo_root: Path, guide: dict[str, str], hacks: dict[str, dict[str, Any]], anchor: str, script: str) -> dict[str, str]:
    if anchor not in guide:
        raise ValueError(f"guide anchor {anchor!r} missing from HACKERS_GUIDE.md")
    if script not in hacks:
        raise ValueError(f"hack script {script!r} missing metadata")
    script_anchor = hacks[script]["guide_anchor"]
    if script_anchor not in guide:
        raise ValueError(f"{script} points to missing guide anchor {script_anchor!r}")
    if anchor not in hacks[script]["guide_anchors"]:
        raise ValueError(f"{script} does not support guide anchor {anchor!r}")
    if not (repo_root / script).exists():
        raise ValueError(f"hack script {script!r} does not exist")
    return {
        "guide_anchor": anchor,
        "guide_title": guide[anchor],
        "hack_script": script,
        "hack_summary": hacks[script]["hack_summary"],
    }


def build(repo_root: Path) -> dict[str, Any]:
    repos = load_repos(repo_root)
    guide = guide_sections(repo_root)
    hacks = read_hack_metadata(repo_root)
    validate_hack_guide_anchors(guide, hacks)
    nodes = [
        {
            "id": "kilvin-client",
            "label": "Kilvin client",
            "layer": "kilvin",
            "kind": "client",
            "summary": "Starts the single training workflow with the model X on FineWeb training config.",
            "notes": "The sample config asks for one clean thing: train model X on FineWeb with 64 A100 GPUs. One KilvinTrainingWorkflow materializes that intent end to end and exposes task queues, activities, retries, heartbeats, and hood-open artifacts.",
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
            "notes": "For the Kilvin-inspired flow, activation drives the training workflow deterministically until it blocks on its next command.",
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
        edge("workflow-complete", "workflow-activation", "core-worker", "completion", "WorkflowActivationCompletion"),
        edge("core-frontend", "core-worker", "frontend-service", "rpc", "worker service RPC"),
        edge("frontend-history", "frontend-service", "history-service", "history-rpc", "route worker response to History"),
        edge("activity-command", "frontend-service", "history-service", "command", "ScheduleActivityTask command"),
        edge("activity-dispatch", "history-service", "matching-service", "task-dispatch", "enqueue activity task"),
        edge("activity-poll", "core-worker", "activity-task", "activation", "ActivityTask"),
        edge("heartbeat", "activity-task", "core-worker", "heartbeat", "RecordHeartbeat"),
        edge("activity-complete", "activity-task", "core-worker", "completion", "ActivityTaskCompleted"),
    ]
    phases = [
        {
            "id": "start",
            "label": "Start workflow",
            "summary": "Kilvin submits the model X training run.",
            "node_ids": ["kilvin-client", "frontend-service", "history-service"],
            **guide_link(repo_root, guide, hacks, "happy-path-start-workflow-to-first-activation", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "poll",
            "label": "Poll task queue",
            "summary": "Worker polling crosses Python, bridge, core, and Matching.",
            "node_ids": ["python-worker", "bridge-worker", "core-worker", "matching-service"],
            **guide_link(repo_root, guide, hacks, "workflow-task-polling-matching---sdk-core---bridge---python", "hacks/003_task_queue_polling.py"),
        },
        {
            "id": "activate",
            "label": "Activate workflow",
            "summary": "Core delivers a workflow activation to Python asyncio code.",
            "node_ids": ["core-worker", "workflow-activation", "python-worker"],
            **guide_link(repo_root, guide, hacks, "workflow-task-polling-matching---sdk-core---bridge---python", "hacks/003_task_queue_polling.py"),
        },
        {
            "id": "schedule-activity",
            "label": "Schedule activity",
            "summary": "Workflow commands become durable history events and activity tasks.",
            "node_ids": ["workflow-activation", "core-worker", "frontend-service", "history-service", "matching-service"],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "execute-activity",
            "label": "Execute activity",
            "summary": "Python runs side-effecting activity code and heartbeats progress.",
            "node_ids": ["activity-task", "core-worker", "frontend-service", "history-service"],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "complete",
            "label": "Complete turn",
            "summary": "Completions update history and may schedule the next workflow task.",
            "node_ids": ["workflow-activation", "core-worker", "frontend-service", "history-service", "matching-service"],
            **guide_link(repo_root, guide, hacks, "history-as-source-of-truth-and-replay", "hacks/004_history_replay.py"),
        },
    ]
    calls = [
        call(
            "call-start-workflow",
            "start",
            1,
            "kilvin-client",
            "frontend-service",
            "start-rpc",
            "rpc",
            "StartWorkflowExecution",
            "Kilvin asks Temporal Frontend to create the training workflow run.",
            [
                "The client sends the workflow type, workflow id, task queue, and the model X training config to the public Temporal API.",
                "Frontend is the first server boundary for the workflow start request.",
            ],
            ["workflow_id", "task_queue", "workflow_type", "model_x_training_config"],
            [
                local_ref(
                    repo_root,
                    "kilvin-py/start_workflow.py",
                    "await client.execute_workflow(",
                    "start_workflow.py",
                    pattern=r"^\s*\w+\s*=\s*await client\.execute_workflow\(",
                )
            ],
        ),
        call(
            "call-record-start",
            "start",
            2,
            "frontend-service",
            "history-service",
            "history-start",
            "history-event",
            "WorkflowExecutionStarted",
            "Frontend routes the accepted start request into History for durable recording.",
            [
                "History appends the initial WorkflowExecutionStarted event so replay can reconstruct the run from event history.",
                "This event stores the workflow input and task queue metadata used by later workflow tasks.",
            ],
            ["event_type=WorkflowExecutionStarted", "workflow_task_queue", "input"],
        ),
        call(
            "call-enqueue-first-workflow-task",
            "start",
            3,
            "history-service",
            "matching-service",
            "schedule-wft",
            "task-dispatch",
            "workflow task",
            "History schedules the first workflow task for Matching to hand to a worker poller.",
            [
                "The durable start event creates work for the configured workflow task queue.",
                "Matching owns the queueing boundary where a polling worker will later receive the task.",
            ],
            ["task_queue", "workflow_task", "scheduled_event_id"],
        ),
        call(
            "call-python-poll-activation",
            "poll",
            4,
            "python-worker",
            "bridge-worker",
            "worker-poll",
            "poll",
            "poll_workflow_activation",
            "The Python worker awaits the next workflow activation through the bridge.",
            [
                "Python initiates the poll because Temporal workers pull tasks rather than receiving direct server callbacks.",
                "The bridge converts the Python await into a core worker poll operation.",
            ],
            ["worker_identity", "workflow_task_queue"],
            [
                ref(
                    repo_root,
                    repos,
                    "sdk-python",
                    "temporalio/bridge/worker.py",
                    "poll_workflow_activation",
                    "Python bridge poll activation",
                    pattern=r"^\s+async def poll_workflow_activation\(",
                )
            ],
        ),
        call(
            "call-bridge-core-poll",
            "poll",
            5,
            "bridge-worker",
            "core-worker",
            "bridge-core",
            "poll",
            "core poller request",
            "The bridge asks sdk-core for the next workflow activation.",
            [
                "The bridge preserves Python's async boundary while delegating polling, cache, and state-machine work to core.",
                "Core can satisfy the request only after it obtains or reconstructs a workflow task.",
            ],
            ["poller_kind=workflow", "task_queue"],
        ),
        call(
            "call-core-poll-matching",
            "poll",
            6,
            "core-worker",
            "matching-service",
            "core-matching",
            "poll",
            "PollWorkflowTaskQueue",
            "sdk-core polls Matching for an available workflow task.",
            [
                "Core issues the server poll request on behalf of the Python worker.",
                "The direction is worker to Matching: the worker is asking the server for work.",
            ],
            ["namespace", "task_queue", "identity"],
            [
                ref(
                    repo_root,
                    repos,
                    "sdk-core",
                    "crates/sdk-core/src/worker/client.rs",
                    "async fn poll_workflow_task",
                    "Core poll workflow task",
                    pattern=r"^\s+async fn poll_workflow_task\(",
                )
            ],
        ),
        call(
            "call-matching-workflow-task",
            "poll",
            7,
            "matching-service",
            "core-worker",
            "core-matching",
            "response",
            "workflow task response",
            "Matching responds to the long poll with the workflow task from the queue.",
            [
                "The response travels back over the same Core-to-Matching poll edge.",
                "The reversed call direction makes the server response explicit without introducing a separate diagram edge.",
            ],
            ["workflow_task_token", "history", "started_event_id"],
        ),
        call(
            "call-core-activation",
            "activate",
            8,
            "core-worker",
            "workflow-activation",
            "activation-up",
            "activation",
            "WorkflowActivation",
            "sdk-core converts the workflow task into a Python workflow activation.",
            [
                "Core applies workflow state-machine rules and prepares jobs for the Python workflow instance.",
                "Python receives an activation rather than raw server history.",
            ],
            ["run_id", "activation_jobs", "history_events"],
        ),
        call(
            "call-workflow-commands-to-core",
            "schedule-activity",
            9,
            "workflow-activation",
            "core-worker",
            "workflow-complete",
            "completion",
            "WorkflowActivationCompletion",
            "Python completes the workflow activation with a ScheduleActivityTask command.",
            [
                "The deterministic workflow turn records the intent to run an activity instead of performing the side effect inline.",
                "The command first returns to sdk-core as part of the workflow activation completion.",
            ],
            ["activity_type", "activity_id", "task_queue", "timeouts"],
        ),
        call(
            "call-core-respond-workflow-task-completed",
            "schedule-activity",
            10,
            "core-worker",
            "frontend-service",
            "core-frontend",
            "completion",
            "RespondWorkflowTaskCompleted",
            "sdk-core sends the completed workflow task and command batch to Frontend.",
            [
                "Core translates the activation completion into the public worker API request.",
                "The request carries the workflow task token plus commands such as ScheduleActivityTask.",
            ],
            ["workflow_task_token", "commands=[ScheduleActivityTask]", "query_results"],
            [
                ref(
                    repo_root,
                    repos,
                    "sdk-core",
                    "crates/sdk-core/src/worker/client.rs",
                    "async fn complete_workflow_task",
                    "Core complete workflow task",
                    pattern=r"^\s+async fn complete_workflow_task\(",
                ),
                ref(
                    repo_root,
                    repos,
                    "temporal",
                    "service/frontend/workflow_handler.go",
                    "RespondWorkflowTaskCompleted",
                    "Frontend RespondWorkflowTaskCompleted",
                    pattern=r"^func \(.*\) RespondWorkflowTaskCompleted\(",
                ),
            ],
        ),
        call(
            "call-history-apply-workflow-task-completed",
            "schedule-activity",
            11,
            "frontend-service",
            "history-service",
            "frontend-history",
            "history-rpc",
            "RespondWorkflowTaskCompleted",
            "Frontend routes the workflow task completion to History.",
            [
                "History records WorkflowTaskCompleted and validates the command batch.",
                "The ScheduleActivityTask command is applied inside the History service transaction.",
            ],
            ["event_type=WorkflowTaskCompleted", "commands=[ScheduleActivityTask]", "workflow_task_token"],
        ),
        call(
            "call-schedule-activity-command",
            "schedule-activity",
            12,
            "frontend-service",
            "history-service",
            "activity-command",
            "command",
            "ScheduleActivityTask command",
            "History applies the ScheduleActivityTask command into durable activity state.",
            [
                "The command creates activity scheduling history and server-side activity state.",
                "Only after the command is accepted can an activity task be enqueued for Matching.",
            ],
            ["event_type=ActivityTaskScheduled", "activity_id", "activity_task_queue"],
        ),
        call(
            "call-enqueue-activity-task",
            "schedule-activity",
            13,
            "history-service",
            "matching-service",
            "activity-dispatch",
            "task-dispatch",
            "activity task",
            "History dispatches the scheduled activity task through Matching.",
            [
                "After accepting the completed workflow task, History records the activity scheduling event and places the task on the target activity queue.",
                "Matching will deliver the task when a compatible worker poll is available.",
            ],
            ["activity_task_queue", "activity_task", "scheduled_event_id"],
        ),
        call(
            "call-core-poll-activity-task",
            "execute-activity",
            14,
            "core-worker",
            "matching-service",
            "core-matching",
            "poll",
            "PollActivityTaskQueue",
            "sdk-core polls Matching for an available activity task.",
            [
                "Core issues an activity task poll after History has enqueued the scheduled activity task.",
                "The direction is worker to Matching: the worker asks the activity task queue for work.",
            ],
            ["namespace", "activity_task_queue", "identity"],
        ),
        call(
            "call-matching-activity-task",
            "execute-activity",
            15,
            "matching-service",
            "core-worker",
            "core-matching",
            "response",
            "activity task response",
            "Matching responds to the activity poll with the queued activity task.",
            [
                "The activity task response travels back over the same Core-to-Matching poll edge.",
                "Core must receive this response before it can deliver the activity task to Python.",
            ],
            ["activity_task_token", "activity_type", "input"],
        ),
        call(
            "call-core-activity-task",
            "execute-activity",
            16,
            "core-worker",
            "activity-task",
            "activity-poll",
            "activation",
            "ActivityTask",
            "sdk-core hands an activity task to Python for execution.",
            [
                "Core receives activity work through its pollers and presents it to Python as an executable activity task.",
                "The activity task can perform the external side effects that workflow code must avoid.",
            ],
            ["activity_type", "task_token", "input", "heartbeat_details"],
        ),
        call(
            "call-activity-heartbeat",
            "execute-activity",
            17,
            "activity-task",
            "core-worker",
            "heartbeat",
            "heartbeat",
            "RecordHeartbeat",
            "The running activity reports progress back through sdk-core.",
            [
                "Heartbeats let Temporal observe liveness and persist progress details for retry or cancellation handling.",
                "Core batches and forwards heartbeat state while Python continues the async activity.",
            ],
            ["task_token", "progress", "heartbeat_details"],
        ),
        call(
            "call-core-record-activity-heartbeat",
            "execute-activity",
            18,
            "core-worker",
            "frontend-service",
            "core-frontend",
            "heartbeat",
            "RecordActivityTaskHeartbeat",
            "sdk-core forwards heartbeat details to Frontend.",
            [
                "Core batches activity heartbeat state and sends it over the worker service API.",
                "The heartbeat response can carry cancellation, pause, or reset information back toward the activity.",
            ],
            ["task_token", "details", "identity"],
            [
                ref(
                    repo_root,
                    repos,
                    "sdk-core",
                    "crates/sdk-core/src/worker/client.rs",
                    "async fn record_activity_heartbeat",
                    "Core record activity heartbeat",
                    pattern=r"^\s+async fn record_activity_heartbeat\(",
                ),
                ref(
                    repo_root,
                    repos,
                    "temporal",
                    "service/frontend/workflow_handler.go",
                    "RecordActivityTaskHeartbeat",
                    "Frontend RecordActivityTaskHeartbeat",
                    pattern=r"^func \(.*\) RecordActivityTaskHeartbeat\(",
                ),
            ],
        ),
        call(
            "call-history-record-activity-heartbeat",
            "execute-activity",
            19,
            "frontend-service",
            "history-service",
            "frontend-history",
            "history-rpc",
            "RecordActivityTaskHeartbeat",
            "Frontend routes heartbeat state into History.",
            [
                "History updates activity progress details and returns cancellation state if requested.",
                "Heartbeat handling does not complete the activity or enqueue a workflow task by itself.",
            ],
            ["task_token", "heartbeat_details", "cancel_requested"],
        ),
        call(
            "call-activity-complete",
            "execute-activity",
            20,
            "activity-task",
            "core-worker",
            "activity-complete",
            "completion",
            "ActivityTaskCompleted",
            "The Python activity returns its result to sdk-core.",
            [
                "The activity returns its output after the side effect finishes.",
                "Core receives the activity completion before it can report the result to the server.",
            ],
            ["task_token", "activity_result"],
        ),
        call(
            "call-core-respond-activity-task-completed",
            "execute-activity",
            21,
            "core-worker",
            "frontend-service",
            "core-frontend",
            "completion",
            "RespondActivityTaskCompleted",
            "sdk-core sends the activity result to Frontend.",
            [
                "Core translates the Python activity completion into the worker service completion RPC.",
                "The RPC carries the activity task token and result payload.",
            ],
            ["task_token", "result", "identity"],
            [
                ref(
                    repo_root,
                    repos,
                    "sdk-core",
                    "crates/sdk-core/src/worker/client.rs",
                    "async fn complete_activity_task",
                    "Core complete activity task",
                    pattern=r"^\s+async fn complete_activity_task\(",
                ),
                ref(
                    repo_root,
                    repos,
                    "temporal",
                    "service/frontend/workflow_handler.go",
                    "RespondActivityTaskCompleted",
                    "Frontend RespondActivityTaskCompleted",
                    pattern=r"^func \(.*\) RespondActivityTaskCompleted\(",
                ),
            ],
        ),
        call(
            "call-history-record-activity-task-completed",
            "execute-activity",
            22,
            "frontend-service",
            "history-service",
            "frontend-history",
            "history-rpc",
            "ActivityTaskCompleted",
            "Frontend routes the activity completion to History for durable recording.",
            [
                "History appends ActivityTaskCompleted so replay can feed the result back to workflow code.",
                "Recording the completion makes the workflow eligible for a follow-up workflow task.",
            ],
            ["event_type=ActivityTaskCompleted", "activity_result", "completed_event_id"],
        ),
        call(
            "call-enqueue-followup-workflow-task",
            "complete",
            23,
            "history-service",
            "matching-service",
            "schedule-wft",
            "task-dispatch",
            "follow-up workflow task",
            "History enqueues another workflow task when new events require workflow code to run again.",
            [
                "Activity completion or command application can make the workflow ready for another deterministic turn.",
                "Matching holds that follow-up workflow task until a worker polls the task queue.",
            ],
            ["task_queue", "workflow_task", "new_history_events"],
        ),
        call(
            "call-core-poll-followup-workflow-task",
            "complete",
            24,
            "core-worker",
            "matching-service",
            "core-matching",
            "poll",
            "PollWorkflowTaskQueue",
            "sdk-core long-polls Matching for the follow-up workflow task.",
            [
                "After History enqueues the follow-up task, Core must poll Matching again before the task can be returned.",
                "This preserves the worker-pull model for follow-up workflow turns as well as the first workflow task.",
            ],
            ["namespace", "task_queue", "identity"],
        ),
        call(
            "call-followup-workflow-task",
            "complete",
            25,
            "matching-service",
            "core-worker",
            "core-matching",
            "response",
            "follow-up workflow task response",
            "Matching returns the follow-up workflow task to sdk-core on the next poll.",
            [
                "The completed activity produced new history, so the next workflow task carries those events back to the worker.",
                "This response uses the same Core-to-Matching poll edge in reverse to show the server response.",
            ],
            ["workflow_task_token", "activity_completed_event", "history"],
        ),
        call(
            "call-followup-activation",
            "complete",
            26,
            "core-worker",
            "workflow-activation",
            "activation-up",
            "activation",
            "WorkflowActivation",
            "sdk-core delivers the follow-up activation so Python can observe the activity result.",
            [
                "Core converts the follow-up workflow task into another deterministic Python activation.",
                "The workflow can now continue from the completed activity result or emit final completion commands.",
            ],
            ["activation_jobs", "activity_result", "history_events"],
        ),
    ]
    return {
        "generated_at": lock_generated_at(repo_root),
        "slug": "kilvin-asyncio-happy-path",
        "label": "Kilvin asyncio happy path",
        "phases": phases,
        "nodes": nodes,
        "edges": edges,
        "calls": calls,
    }


def control_scenarios(repo_root: Path, guide: dict[str, str], hacks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "slug": "pause-resume",
            "label": "Pause / resume",
            "summary": "Signals or updates change durable workflow state; replay rebuilds the same pause decision before the workflow continues.",
            "highlight_node_ids": ["workflow-activation", "history-service"],
            "highlight_edge_ids": ["workflow-complete", "schedule-wft"],
            "details": [
                "Python workflow code records pause state through deterministic workflow state.",
                "History stores signal or update events so the decision survives worker restarts.",
                "sdk-core replays the event history before delivering a new activation.",
            ],
            "steps": [
                control_step(
                    "pause-resume-signal-recorded",
                    1,
                    "signal",
                    "SignalWorkflowExecution",
                    "A pause or resume request enters workflow history through the server.",
                    [
                        "External control arrives as a signal or update instead of mutating worker memory directly.",
                        "History records the event so the control state survives worker restarts.",
                    ],
                    source="frontend-service",
                    target="history-service",
                    edge_id="frontend-history",
                    affected_node_ids=["frontend-service", "history-service"],
                    affected_edge_ids=["frontend-history"],
                ),
                control_step(
                    "pause-resume-activation",
                    2,
                    "activation",
                    "WorkflowActivation(signal/update)",
                    "The next activation delivers the durable control event to Python workflow code.",
                    [
                        "sdk-core includes the signal or update job in the activation.",
                        "Python workflow code updates deterministic pause state from that activation.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "pause-resume-command",
                    3,
                    "command",
                    "RespondWorkflowTaskCompleted",
                    "Python emits commands that either wait while paused or continue after resume.",
                    [
                        "The pause decision is encoded in deterministic workflow state.",
                        "Completion commands return through sdk-core and History like the happy path.",
                    ],
                    source="workflow-activation",
                    target="core-worker",
                    edge_id="workflow-complete",
                    affected_node_ids=["workflow-activation", "core-worker"],
                    affected_edge_ids=["workflow-complete"],
                ),
            ],
            **guide_link(repo_root, guide, hacks, "pause-resume-as-signalupdate-driven-coordination", "hacks/005_control_paths.py"),
        },
        {
            "slug": "retry",
            "label": "Retry",
            "summary": "Activity failure is recorded durably, then server retry policy and worker polling produce the next attempt.",
            "highlight_node_ids": ["activity-task", "history-service", "matching-service"],
            "highlight_edge_ids": ["activity-complete", "activity-dispatch"],
            "details": [
                "The Python activity reports failure, timeout, or cancellation through sdk-core.",
                "History records the outcome and computes retry scheduling from policy.",
                "Matching dispatches the next activity task when the retry is due.",
            ],
            "steps": [
                control_step(
                    "retry-failure",
                    1,
                    "failure",
                    "RespondActivityTaskFailed",
                    "The Python activity reports failure, timeout, or cancellation through sdk-core.",
                    [
                        "The failed attempt is not retried in Python user code directly.",
                        "The failure is reported back to the server as an activity completion outcome.",
                    ],
                    source="activity-task",
                    target="core-worker",
                    edge_id="activity-complete",
                    affected_node_ids=["activity-task", "core-worker"],
                    affected_edge_ids=["activity-complete"],
                ),
                control_step(
                    "retry-policy",
                    2,
                    "timer",
                    "Activity retry timer",
                    "History records the failed attempt and applies retry policy timing.",
                    [
                        "Retry state is durable server state.",
                        "Backoff determines when the next attempt becomes eligible.",
                    ],
                    source="history-service",
                    target="matching-service",
                    edge_id="activity-dispatch",
                    affected_node_ids=["history-service", "matching-service"],
                    affected_edge_ids=["activity-dispatch"],
                ),
                control_step(
                    "retry-dispatch",
                    3,
                    "task-dispatch",
                    "PollActivityTaskQueueResponse",
                    "Matching dispatches the next activity task attempt when the retry is due.",
                    [
                        "A worker poll receives the next attempt as normal activity work.",
                        "The retry re-enters Python through the same activity execution path.",
                    ],
                    source="history-service",
                    target="matching-service",
                    edge_id="activity-dispatch",
                    affected_node_ids=["history-service", "matching-service"],
                    affected_edge_ids=["activity-dispatch"],
                ),
            ],
            **guide_link(repo_root, guide, hacks, "retry-and-failure-handling", "hacks/005_control_paths.py"),
        },
        {
            "slug": "replay",
            "label": "Replay",
            "summary": "History events rebuild workflow state before new commands are accepted.",
            "highlight_node_ids": ["history-service", "core-worker", "workflow-activation"],
            "highlight_edge_ids": ["activation-up", "workflow-complete"],
            "details": [
                "History is the authoritative log of prior workflow decisions.",
                "sdk-core rebuilds workflow state machines from that log.",
                "sdk-python re-executes deterministic workflow code without re-running activity side effects.",
            ],
            "steps": [
                control_step(
                    "replay-history-read",
                    1,
                    "history-event",
                    "GetWorkflowExecutionHistory",
                    "sdk-core reads durable history before accepting new workflow commands.",
                    [
                        "History is the authoritative log of prior workflow decisions.",
                        "Worker memory is an optimization, not the source of truth.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "replay-activation",
                    2,
                    "activation",
                    "WorkflowActivation(replay)",
                    "sdk-core replays history into Python workflow code deterministically.",
                    [
                        "Python re-executes workflow code to rebuild local state.",
                        "Activity side effects are not re-run during workflow replay.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "replay-command-check",
                    3,
                    "completion",
                    "RespondWorkflowTaskCompleted",
                    "New commands are accepted only after replay catches up to history.",
                    [
                        "Determinism requires replayed commands to match recorded history.",
                        "After catch-up, newly emitted commands can advance the execution.",
                    ],
                    source="workflow-activation",
                    target="core-worker",
                    edge_id="workflow-complete",
                    affected_node_ids=["workflow-activation", "core-worker"],
                    affected_edge_ids=["workflow-complete"],
                ),
            ],
            **guide_link(repo_root, guide, hacks, "history-as-source-of-truth-and-replay", "hacks/004_history_replay.py"),
        },
        {
            "slug": "heartbeat-cancellation",
            "label": "Heartbeat cancellation",
            "summary": "Activity heartbeats carry progress and provide cancellation checkpoints across Python, sdk-core, and server state.",
            "highlight_node_ids": ["activity-task", "core-worker", "history-service"],
            "highlight_edge_ids": ["heartbeat", "activity-complete"],
            "details": [
                "The Python activity heartbeats while performing side effects.",
                "sdk-core forwards heartbeat state and observes cancellation delivery.",
                "The server tracks cancellation/progress state for the activity attempt.",
            ],
            "steps": [
                control_step(
                    "heartbeat-cancellation-progress",
                    1,
                    "heartbeat",
                    "RecordActivityTaskHeartbeat",
                    "The Python activity heartbeats progress while performing side effects.",
                    [
                        "Heartbeat details let retry resume with known progress.",
                        "Heartbeat cadence defines where cancellation can be observed.",
                    ],
                    source="activity-task",
                    target="core-worker",
                    edge_id="heartbeat",
                    affected_node_ids=["activity-task", "core-worker"],
                    affected_edge_ids=["heartbeat"],
                ),
                control_step(
                    "heartbeat-cancellation-server-state",
                    2,
                    "heartbeat",
                    "RecordActivityTaskHeartbeatRequest",
                    "sdk-core forwards heartbeat details and receives cancellation state.",
                    [
                        "The server tracks the latest heartbeat details for the activity attempt.",
                        "Cancellation requested state can be delivered in the heartbeat response.",
                    ],
                    source="core-worker",
                    target="activity-task",
                    edge_id="heartbeat",
                    affected_node_ids=["core-worker", "activity-task"],
                    affected_edge_ids=["heartbeat"],
                ),
                control_step(
                    "heartbeat-cancellation-cancel-complete",
                    3,
                    "completion",
                    "RespondActivityTaskCanceled",
                    "The activity reports cancellation after observing it at a heartbeat checkpoint.",
                    [
                        "Python cleanup runs at the activity boundary.",
                        "History records the canceled activity outcome durably.",
                    ],
                    source="activity-task",
                    target="core-worker",
                    edge_id="activity-complete",
                    affected_node_ids=["activity-task", "core-worker"],
                    affected_edge_ids=["activity-complete"],
                ),
            ],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/005_control_paths.py"),
        },
        {
            "slug": "sticky-cache-eviction",
            "label": "Sticky cache eviction",
            "summary": "Core cache eviction falls back to replay because History, not worker memory, is authoritative.",
            "highlight_node_ids": ["core-worker", "history-service", "matching-service"],
            "highlight_edge_ids": ["core-matching", "activation-up"],
            "details": [
                "sdk-core may keep workflow state warm in a sticky cache.",
                "Eviction or sticky miss sends execution back through history replay.",
                "Python receives a rebuilt activation after core catches up to the latest history.",
            ],
            "steps": [
                control_step(
                    "sticky-cache-eviction-miss",
                    1,
                    "cache",
                    "Sticky cache miss",
                    "sdk-core discovers that warm workflow state is unavailable.",
                    [
                        "Sticky cache state is an optimization for faster activations.",
                        "Eviction or worker movement requires rebuilding from history.",
                    ],
                    source="matching-service",
                    target="core-worker",
                    edge_id="core-matching",
                    affected_node_ids=["matching-service", "core-worker"],
                    affected_edge_ids=["core-matching"],
                ),
                control_step(
                    "sticky-cache-eviction-replay",
                    2,
                    "history-event",
                    "Replay from History",
                    "Core falls back to history replay because History is authoritative.",
                    [
                        "The replay path reconstructs workflow state without relying on sticky memory.",
                        "This keeps correctness independent of worker cache residency.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "sticky-cache-eviction-rebuilt-activation",
                    3,
                    "activation",
                    "WorkflowActivation(rebuilt)",
                    "Python receives a rebuilt activation after core catches up to history.",
                    [
                        "The workflow continues with deterministic state restored.",
                        "Future tasks may become sticky again after the rebuilt activation.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
            ],
            **guide_link(repo_root, guide, hacks, "sticky-workflow-cache-and-eviction", "hacks/005_control_paths.py"),
        },
    ]


def _guide_section(guide: dict[str, str], anchor: str) -> dict[str, str]:
    if anchor not in guide:
        raise ValueError(f"guide anchor {anchor!r} missing from HACKERS_GUIDE.md")
    return {"guide_anchor": anchor, "guide_title": guide[anchor]}


def kilvin_internals(repo_root: Path, guide: dict[str, str]) -> dict[str, Any]:
    """Business-logic manifest: what KilvinTrainingWorkflow and its activities do."""

    def step(
        step_id: str,
        seq: int,
        label: str,
        activity_fn: str,
        summary: str,
        details: list[str],
        *,
        input_model: str,
        output_model: str,
        timeout_seconds: int,
        heartbeat: bool = False,
        artifacts: list[str],
        guide_anchor: str,
    ) -> dict[str, Any]:
        return {
            "id": step_id,
            "seq": seq,
            "label": label,
            "activity": activity_fn,
            "summary": summary,
            "details": details,
            "input_model": input_model,
            "output_model": output_model,
            "timeout_seconds": timeout_seconds,
            "retry": "3 attempts, 5s initial backoff",
            "heartbeat": heartbeat,
            "artifacts": artifacts,
            **_guide_section(guide, guide_anchor),
            "refs": [
                local_ref(
                    repo_root,
                    "kilvin-py/kilvin_py/activities.py",
                    f"async def {activity_fn}(",
                    f"{activity_fn} activity",
                    pattern=rf"^async def {activity_fn}\(",
                ),
                local_ref(
                    repo_root,
                    "kilvin-py/kilvin_py/workflows.py",
                    f'step_name="{step_id}"',
                    "workflow call site",
                    pattern=rf'step_name="{step_id}",',
                ),
            ],
        }

    return {
        "generated_at": lock_generated_at(repo_root),
        "workflow": {
            "name": "KilvinTrainingWorkflow",
            "task_queue": "kilvin-training-task-queue",
            "summary": "One workflow materializes one training intent end to end: from a researcher's run config to a monitored Kubernetes job.",
            "details": [
                "The workflow validates the run config, interprets the intent into a typed plan, concretizes dependencies once, then runs allocate -> materialize -> submit -> monitor for each enabled stage.",
                "Every step goes through the same durable envelope (_run_step): check cancellation, honor pause gates, check replay-skip, persist the step input as in.yaml, execute the activity with a retry policy, persist the result as out.yaml, and append a typed step trace.",
                "Because the trace and pause/replay state live in workflow state rebuilt from History, the run survives worker restarts and stays inspectable mid-flight through queries.",
            ],
            **_guide_section(guide, "running-example-kilvin-inspired-training-workflow"),
            "refs": [
                local_ref(
                    repo_root,
                    "kilvin-py/kilvin_py/workflows.py",
                    "class KilvinTrainingWorkflow",
                    "KilvinTrainingWorkflow",
                    pattern=r"^class KilvinTrainingWorkflow:",
                ),
                local_ref(
                    repo_root,
                    "kilvin-py/kilvin_py/workflows.py",
                    "async def _run_step",
                    "step envelope (_run_step)",
                    pattern=r"^\s+async def _run_step\(",
                ),
                local_ref(
                    repo_root,
                    "kilvin-py/worker.py",
                    "Worker(",
                    "worker registration",
                ),
            ],
        },
        "steps": [
            step(
                "interpret_intent",
                1,
                "Interpret training intent",
                "interpret_training_intent",
                "Turns the researcher's run config into the typed plan the rest of the workflow executes.",
                [
                    "Reads the run config and job params URI and resolves the base checkpoint, the workflow config URI, and a component profile (run name, model, dataset root, spec version).",
                    "Everything downstream consumes this TrainingIntent instead of re-parsing raw config, so the plan is decided once and recorded durably.",
                ],
                input_model="InterpretIntentInput",
                output_model="TrainingIntent",
                timeout_seconds=30,
                artifacts=["{stage}/interpret_intent/in.yaml", "{stage}/interpret_intent/out.yaml"],
                guide_anchor="running-example-kilvin-inspired-training-workflow",
            ),
            step(
                "concretize_dependencies",
                2,
                "Concretize dependencies",
                "concretize_dependencies",
                "Builds the training image and pins dependencies into a concrete code bundle.",
                [
                    "Produces an auto job id and a code bundle key derived from the intent's checkpoint, so later stages launch from an immutable artifact instead of a mutable branch.",
                    "Runs once per workflow, before the per-stage loop: every stage shares the same pinned code bundle.",
                ],
                input_model="ConcretizeDependenciesInput",
                output_model="ConcretizeDependenciesOutput",
                timeout_seconds=120,
                artifacts=["{stage}/concretize_dependencies/in.yaml", "{stage}/concretize_dependencies/out.yaml"],
                guide_anchor="running-example-kilvin-inspired-training-workflow",
            ),
            step(
                "allocate_resources",
                3,
                "Allocate resources",
                "allocate_resources",
                "Gathers quota and placement constraints, solves placement, and reserves the GPU allocation.",
                [
                    "Resolves the cluster, racks, node pool, RDMA/NCCL networking profile, rendezvous endpoint, and dataset mount for the stage's requested shape (8 nodes x 8 A100s).",
                    "The QuotaDecision explains why the placement was granted; the workflow persists it as quota_decision.yaml so the reasoning is inspectable after the fact.",
                ],
                input_model="AllocateResourcesInput",
                output_model="ReamAllocationOutput",
                timeout_seconds=180,
                artifacts=[
                    "{stage}/allocate_resources/in.yaml",
                    "{stage}/allocate_resources/out.yaml",
                    "{stage}/allocate_resources/quota_decision.yaml",
                ],
                guide_anchor="retry-and-failure-handling",
            ),
            step(
                "materialize_training_bundle",
                4,
                "Materialize training bundle",
                "materialize_training_bundle",
                "Expands the intent plus the allocation into the concrete launch spec for this stage.",
                [
                    "Binds components to machines, computes the token budget and learning-rate plan, assembles env vars and the launch plan, and lists health checks (NCCL rings, KV router, data loader, RDMA topology).",
                    "This is the 10-lines-of-intent to 1000-line-spec moment; env_vars.yaml is persisted separately because wrong env vars are the most common thing to debug.",
                ],
                input_model="MaterializeTrainingBundleInput",
                output_model="MaterializedBundleOutput",
                timeout_seconds=180,
                artifacts=[
                    "{stage}/materialize_training_bundle/in.yaml",
                    "{stage}/materialize_training_bundle/out.yaml",
                    "{stage}/materialize_training_bundle/env_vars.yaml",
                ],
                guide_anchor="running-example-kilvin-inspired-training-workflow",
            ),
            step(
                "submit_k8s_job",
                5,
                "Submit Kubernetes job",
                "submit_k8s_job",
                "Submits the materialized bundle as a job in the kilvin-training namespace.",
                [
                    "Returns the generated job name, the Primus job id, and the monitoring UI URL that the workflow records for operators.",
                    "Submission is intentionally separate from monitoring so a retry resubmits cleanly without confusing the watch loop.",
                ],
                input_model="SubmitK8sInput",
                output_model="SubmitK8sOutput",
                timeout_seconds=180,
                artifacts=["{stage}/submit_k8s_job/in.yaml", "{stage}/submit_k8s_job/out.yaml"],
                guide_anchor="running-example-kilvin-inspired-training-workflow",
            ),
            step(
                "monitor_training",
                6,
                "Monitor training",
                "monitor_training",
                "Watches the running job and heartbeats progress until it reaches a final status.",
                [
                    "Heartbeats carry the job name, Primus id, and namespace so a retried attempt resumes with context and cancellation has a checkpoint to land on.",
                    "Log pointers are persisted as logs.yaml before the failure check, so a failed stage still leaves its logs artifact open for debugging; a failed final status raises and fails the stage.",
                ],
                input_model="MonitorTrainingInput",
                output_model="MonitorOutput",
                timeout_seconds=3600,
                heartbeat=True,
                artifacts=[
                    "{stage}/monitor_training/in.yaml",
                    "{stage}/monitor_training/out.yaml",
                    "{stage}/monitor_training/logs.yaml",
                ],
                guide_anchor="activity-execution-and-heartbeats",
            ),
        ],
        "signals": [
            {"name": "pause", "summary": "Park the run before the next step; durable even if no worker is polling yet."},
            {"name": "resume", "summary": "Clear the pause and let the workflow continue from exactly where it parked."},
            {"name": "pause_at_step", "summary": "Arm a one-shot breakpoint: pause before (pre) or after (post) a named stage/step."},
            {"name": "replay_step", "summary": "Bump the run attempt and re-run from a target stage or step, skipping earlier work with recorded skip artifacts."},
            {"name": "cancel", "summary": "Mark the run cancelled; the next step boundary raises a non-retryable error."},
        ],
        "queries": [
            {"name": "run_status", "summary": "The full KilvinRunState: current stage/step, paused flag, traces, and failures."},
            {"name": "run_step_trace", "summary": "Every step execution envelope with status, checksums, and artifact pointers."},
            {"name": "run_artifacts", "summary": "Flat list of every YAML artifact URI the run has written so far."},
            {"name": "run_plan", "summary": "The ordered stage ids the workflow resolved from the run config."},
        ],
        "control_refs": [
            local_ref(
                repo_root,
                "kilvin-py/kilvin_py/workflows.py",
                "def pause(",
                "signal handlers",
                pattern=r"^\s+def pause\(",
            ),
            local_ref(
                repo_root,
                "kilvin-py/kilvin_py/workflows.py",
                "def run_status(",
                "query handlers",
                pattern=r"^\s+def run_status\(",
            ),
        ],
        "control_guide": _guide_section(guide, "pause-resume-as-signalupdate-driven-coordination"),
        "artifact_root": ".kilvin-artifacts/{run_id}/{attempt}/artifacts/{stage}/{step}/",
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_public_guide(repo_root: Path) -> None:
    source = repo_root / "HACKERS_GUIDE.md"
    target = repo_root / "explorer" / "public" / "HACKERS_GUIDE.md"
    markdown = source.read_text(encoding="utf-8")
    target.write_text(markdown, encoding="utf-8")
    (repo_root / "explorer" / "public" / "data" / "guide.md").write_text(
        markdown,
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    out = repo_root / "explorer" / "public" / "data"
    guide = guide_sections(repo_root)
    hacks = read_hack_metadata(repo_root)
    validate_hack_guide_anchors(guide, hacks)
    write_public_guide(repo_root)

    lifecycle = build(repo_root)
    write_json(out / "lifecycle" / "kilvin-asyncio-happy-path.json", lifecycle)
    write_json(
        out / "lifecycle" / "index.json",
        [{"slug": lifecycle["slug"], "label": lifecycle["label"], "manifest": "lifecycle/kilvin-asyncio-happy-path.json"}],
    )

    write_json(out / "kilvin" / "internals.json", kilvin_internals(repo_root, guide))

    scenarios = control_scenarios(repo_root, guide, hacks)
    write_json(
        out / "control-paths" / "index.json",
        [{"slug": s["slug"], "label": s["label"], "manifest": f"control-paths/{s['slug']}.json"} for s in scenarios],
    )
    for scenario in scenarios:
        write_json(out / "control-paths" / f"{scenario['slug']}.json", scenario)

    write_json(
        out / "guide" / "index.json",
        {
            "guide": "HACKERS_GUIDE.md",
            "sections": [{"anchor": anchor, "title": title} for anchor, title in sorted(guide.items())],
            "hacks": [{"script": script, **meta} for script, meta in sorted(hacks.items())],
        },
    )

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
