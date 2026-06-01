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
        "refs": [],
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
        {
            "id": "start",
            "label": "Start workflow",
            "summary": "Kilvin submits a staged training run.",
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
            "node_ids": ["workflow-activation", "history-service", "matching-service"],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "execute-activity",
            "label": "Execute activity",
            "summary": "Python runs side-effecting activity code and heartbeats progress.",
            "node_ids": ["activity-task", "core-worker", "history-service"],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "complete",
            "label": "Complete turn",
            "summary": "Completions update history and may schedule the next workflow task.",
            "node_ids": ["workflow-activation", "history-service", "matching-service"],
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
            "Kilvin asks Temporal Frontend to create the command workflow run.",
            [
                "The client sends the workflow type, workflow id, task queue, and staged training input to the public Temporal API.",
                "Frontend is the first server boundary for the workflow start request.",
            ],
            ["workflow_id", "task_queue", "workflow_type", "staged_training_config"],
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
            "call-schedule-activity-command",
            "schedule-activity",
            9,
            "workflow-activation",
            "history-service",
            "activity-command",
            "command",
            "ScheduleActivityTask command",
            "Workflow code emits a command to schedule side-effecting activity work.",
            [
                "The deterministic workflow turn records the intent to run an activity instead of performing the side effect inline.",
                "History will turn the command into durable activity scheduling state.",
            ],
            ["activity_type", "activity_id", "task_queue", "timeouts"],
        ),
        call(
            "call-workflow-task-complete",
            "schedule-activity",
            10,
            "workflow-activation",
            "history-service",
            "workflow-complete",
            "completion",
            "RespondWorkflowTaskCompleted",
            "The workflow activation completes its turn with the ScheduleActivityTask command batch.",
            [
                "Python returns the workflow task completion after the activation reaches a deterministic blocking point.",
                "History applies the ScheduleActivityTask command from the completion before it can create activity scheduling state.",
            ],
            ["workflow_task_token", "commands=[ScheduleActivityTask]", "query_results"],
        ),
        call(
            "call-enqueue-activity-task",
            "schedule-activity",
            11,
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
            12,
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
            13,
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
            14,
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
            15,
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
            "call-activity-complete",
            "execute-activity",
            16,
            "activity-task",
            "history-service",
            "activity-complete",
            "completion",
            "ActivityTaskCompleted",
            "The activity result is recorded by History as a completed activity event.",
            [
                "The activity returns its output after the side effect finishes.",
                "History appends ActivityTaskCompleted so a later workflow task can consume the result deterministically.",
            ],
            ["task_token", "activity_result", "completed_event_id"],
        ),
        call(
            "call-enqueue-followup-workflow-task",
            "complete",
            17,
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
            "call-followup-workflow-task",
            "complete",
            18,
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
            19,
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
            **guide_link(repo_root, guide, hacks, "sticky-workflow-cache-and-eviction", "hacks/005_control_paths.py"),
        },
    ]


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
