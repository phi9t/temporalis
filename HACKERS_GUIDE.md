# Temporal Hacker's Guide

> A code-first guide to how a Kilvin-inspired Python asyncio workflow moves through sdk-python, the Python bridge, sdk-core, and the Temporal server. Read the happy path first; the advanced control paths are extensions of that same event-sourced loop.

## 1. How to read this guide

Start with the Kilvin running example, then follow each section's source map and `hacks/NNN_*.py` probe. The scripts are intentionally small and mostly offline: they inspect generated explorer manifests and source-grounded refs instead of requiring a live Temporal cluster.

## 2. 30-second architecture

Temporal has four boundaries that matter for this guide: the Python client/worker surface, the Python bridge, sdk-core, and the server. The server owns durable workflow identity, History, Matching, timers, and retry scheduling. sdk-core owns worker polling, workflow cache, activations, completions, activity heartbeats, and replay mediation. sdk-python owns user-code scheduling on asyncio and converts Python workflow/activity code into bridge calls.

## 3. Running example: Kilvin-inspired training workflow

The running example is a parent workflow that starts a staged training run, schedules activities for resource allocation and workload materialization, starts or coordinates child work, monitors progress through a heartbeating activity, and cleans up resources. It is intentionally richer than a greeting workflow because it exposes task queues, child workflows, retries, heartbeats, cancellation, pause/resume, and replay.

## 4. Happy path: start workflow to first activation

User-level event: Kilvin calls the Python client to start a workflow. Temporal boundary: `StartWorkflowExecution` crosses from client into Frontend. Server ownership: Frontend validates and routes the request, History appends the start event and schedules the first workflow task, Matching makes that task available on a task queue. sdk-core ownership: a worker poller receives the task and builds a workflow activation. Python ownership: sdk-python resumes workflow code until it emits commands or blocks.

Try it: `python hacks/002_lifecycle_manifest.py`

## 5. Workflow task polling: Matching -> sdk-core -> bridge -> Python

User-level event: a Python worker appears to await work. Temporal boundary: the worker crosses poll and completion APIs. sdk-core ownership: pollers, slots, workflow-task responses, activations, completion translation, and sticky-cache decisions. Server ownership: Matching hands out workflow tasks and History accepts completions. Deterministic contract: Python workflow code must make the same decisions when replayed from the same history.

Try it: `python hacks/003_task_queue_polling.py`

## 6. Activity execution and heartbeats

Activities are side-effecting work. The workflow schedules an activity command; History records activity task scheduling; Matching dispatches the activity task; sdk-core polls and sends it through the bridge; sdk-python runs the async activity. Heartbeats are progress and cancellation checkpoints owned by activity code at the user level and mediated by sdk-core/server state underneath.

Try it: `python hacks/002_lifecycle_manifest.py`

## 7. History as source of truth and replay

History is the durable log. Workflow memory is a cache, not the source of truth. On replay, sdk-core feeds history back into the workflow state machines and sdk-python re-executes deterministic workflow code to rebuild state before accepting new commands. Activities do not replay their side effects; their completed results are read from history.

Try it: `python hacks/004_history_replay.py`

## 8. Retry and failure handling

Activity failures, timeouts, and worker crashes become durable history decisions. The server records failure events and schedules retries when policy allows. sdk-core reports task outcomes and later polls retry tasks. Python code sees either successful results, retry exhaustion, cancellation, or workflow-task failure depending on where the failure occurs.

Try it: `python hacks/005_control_paths.py`

## 9. Pause/resume as signal/update-driven coordination

Pause/resume is workflow state, not process state. A signal or update records intent in history, workflow code observes it during activation, and future commands reflect the new state. Replay must rebuild the same pause state from history before the workflow continues.

Try it: `python hacks/005_control_paths.py`

## 10. Sticky workflow cache and eviction

Sticky execution lets sdk-core keep workflow state warm for a worker. Eviction is safe because History remains authoritative. On a sticky miss or cache eviction, core rebuilds state through replay and then delivers the next activation to Python.

Try it: `python hacks/005_control_paths.py`

## 11. Where to inspect source next

Use the explorer's source refs for exact line anchors. Start with Kilvin's client and worker files, then sdk-python worker loops, bridge worker calls, sdk-core worker initialization and pollers, and Temporal server Frontend, History, and Matching handlers.

Try it: `python hacks/001_source_map.py`

## 12. Hands-on hacks

Run `python hacks/001_source_map.py` first, then `002`, `003`, `004`, and `005`. `006_optional_local_run.py` is opt-in and should not be part of default verification.
