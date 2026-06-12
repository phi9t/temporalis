# Temporal Hacker's Guide

> A code-first guide to how a Kilvin-inspired Python asyncio workflow — one clean request to train model X on FineWeb with 64 A100 GPUs — moves through sdk-python, the Python bridge, sdk-core, and the Temporal server. Read the happy path first; the advanced control paths are extensions of that same event-sourced loop.

<a id="how-to-read-this-guide"></a>
## 1. How to read this guide

Start with the Kilvin running example, then follow each section's source map and `hacks/NNN_*.py` probe. The scripts are intentionally small and mostly offline: they inspect generated explorer manifests and source-grounded refs instead of requiring a live Temporal cluster.

This guide is one of four tracks in the explorer's Deep Dive view, and the other three are the same material in diagram form: the Lifecycle track animates the happy path of sections 4-6, the Control Paths track overlays sections 7-10 onto that swimlane, and the Kilvin Internals track walks the business logic of section 3 step by step. Read a section here, then watch it move there — each lifecycle phase and control scenario links back to its section in this guide.

<a id="30-second-architecture"></a>
## 2. 30-second architecture

Temporal has four boundaries that matter for this guide: the Python client/worker surface, the Python bridge, sdk-core, and the server. The server owns durable workflow identity, History, Matching, timers, and retry scheduling. sdk-core owns worker polling, workflow cache, activations, completions, activity heartbeats, and replay mediation. sdk-python owns user-code scheduling on asyncio and converts Python workflow/activity code into bridge calls.

<a id="running-example-kilvin-inspired-training-workflow"></a>
## 3. Running example: Kilvin-inspired training workflow

The running example is one clean request: train model X on FineWeb with 64 A100 GPUs. A single `KilvinTrainingWorkflow` on the `kilvin-training-task-queue` materializes that intent end to end: it interprets the training intent into a typed plan, concretizes dependencies (runs `uv lock`, builds and pushes the trainer image, pins the digest), allocates resources (reserves CPU quota from a local allocator service with a finite ledger), materializes the training bundle (the concrete Job manifest plus env vars), submits the Kubernetes job to the k3s cluster from the compose stack, and monitors it through a heartbeating activity. The intent is production-shaped; locally the same workflow materializes it for real at laptop scale — a tiny CPU GPT-2 on tiny-shakespeare. Every step persists hood-open YAML artifacts under `.kilvin-artifacts/` — the materialized job spec, quota decision, env vars, dataset mount, Kubernetes job id, and log pointers — so the run stays inspectable while it executes and after it fails. It is intentionally richer than a greeting workflow because one workflow exposes task queues, activities, retries, heartbeats, cancellation, pause/resume, and replay.

The explorer's Deep Dive -> Kilvin Internals track renders this same workflow from a generated manifest: each step with its activity, typed input/output models, timeout and retry policy, and the artifacts it persists, plus the signal/query control surface. The source refs there resolve to exact lines in `kilvin-py/kilvin_py/workflows.py` and `activities.py`, so the panel and the implementation cannot drift silently.

<a id="happy-path-start-workflow-to-first-activation"></a>
## 4. Happy path: start workflow to first activation

User-level event: Kilvin calls the Python client to start a workflow. Temporal boundary: `StartWorkflowExecution` crosses from client into Frontend. Server ownership: Frontend validates and routes the request, History appends the start event and schedules the first workflow task, Matching makes that task available on a task queue. sdk-core ownership: a worker poller receives the task and builds a workflow activation. Python ownership: sdk-python resumes workflow code until it emits commands or blocks.

Try it: `python hacks/002_lifecycle_manifest.py`

<a id="workflow-task-polling-matching---sdk-core---bridge---python"></a>
## 5. Workflow task polling: Matching -> sdk-core -> bridge -> Python

- User-level event: a Kilvin worker starts `Worker.run()` and appears to block on asyncio work. No user workflow function is called until a workflow task is matched to that worker.
- Temporal boundary: the long poll crosses Python -> bridge -> sdk-core -> Matching as `PollWorkflowTaskQueue`; completion crosses back as `RespondWorkflowTaskCompleted`.
- sdk-core ownership: core owns poller concurrency, slot accounting, sticky routing decisions, conversion from poll responses into workflow activations, and conversion from Python completions into server commands.
- Server ownership: History creates workflow tasks after history changes, Matching holds task queues and matches a polling worker, and History validates completions before appending new events.
- Deterministic contract: workflow code may only emit decisions that can be reproduced from the same history. A poll response can contain old history for replay plus new work; Python must not branch on wall clock, randomness, process state, or prior in-memory cache state.
- Failure behavior: if the worker crashes while polling, the server still owns the task. If Python fails a workflow task, sdk-core reports a failed completion, History records or reschedules as appropriate, and the next task replays from durable history.
- Source map: `kilvin-py/worker.py:Worker(`, `sdk-python/temporalio/worker/_workflow.py:async def run`, `sdk-python/temporalio/bridge/worker.py:poll_workflow_activation`, `sdk-core/crates/sdk-core/src/worker/mod.rs:poll_workflow_activation`, `sdk-core/crates/sdk-core/src/worker/client.rs:PollWorkflowTaskQueueRequest`, `temporal/service/matching/handler.go:PollWorkflowTaskQueue`, and `temporal/service/history/handler.go:RespondWorkflowTaskCompleted`.
- Try it command: `python hacks/003_task_queue_polling.py`; look for the Python worker, bridge worker, core worker, and Matching refs printed as one poll chain.

<a id="activity-execution-and-heartbeats"></a>
## 6. Activity execution and heartbeats

- User-level event: a workflow schedules a side-effecting activity such as real allocator HTTP reservation or k8s training monitoring, then awaits its result. Activity code can touch external systems; workflow code cannot.
- Temporal boundary: `ScheduleActivityTask` leaves workflow completion, the activity worker polls `PollActivityTaskQueue`, and completion or failure returns through `RespondActivityTaskCompleted` or `RespondActivityTaskFailed`. Heartbeats cross the `RecordActivityTaskHeartbeat` boundary.
- sdk-core ownership: core owns activity pollers, task slots, heartbeat throttling, cancellation delivery from heartbeat responses, activity completion reporting, and the bridge payloads handed to sdk-python.
- Server ownership: History records scheduled, started, completed, failed, timed out, or canceled activity events. Matching dispatches activity tasks. Server-side activity timeout and retry state decides whether another attempt is scheduled.
- Deterministic contract: workflow replay observes recorded activity results instead of re-running side effects. Activity code may be nondeterministic, but it must tolerate retries because the server can schedule another attempt after timeout or failure.
- Failure behavior: a worker crash loses only process memory; the activity can time out and retry from server state. A heartbeat failure can surface cancellation to Python, and missing heartbeats can cause heartbeat timeout if configured.
- Source map: `kilvin-py/kilvin_py/activities.py:allocate_resources`, `kilvin-py/kilvin_py/activities.py:monitor_training`, `sdk-python/temporalio/worker/_activity.py:async def run`, `sdk-python/temporalio/bridge/worker.py:poll_activity_task`, `sdk-python/temporalio/bridge/worker.py:record_activity_heartbeat`, `sdk-core/crates/sdk-core-c-bridge/src/worker.rs:temporal_core_worker_record_activity_heartbeat`, and `sdk-core/crates/sdk-core/src/worker/client.rs:record_activity_heartbeat`.
- Try it command: `python hacks/002_lifecycle_manifest.py`; look for the schedule and execute activity phases, then use `python hacks/005_control_paths.py` for heartbeat cancellation details.

<a id="history-as-source-of-truth-and-replay"></a>
## 7. History as source of truth and replay

- User-level event: a workflow resumes after a new event, worker restart, sticky miss, or cache eviction. It may look like Python is continuing local state, but local memory is only an optimization.
- Temporal boundary: History is fetched through workflow-task polling and delivered as activation jobs through sdk-core and the bridge. Python returns commands only after replay has caught up to the current event.
- sdk-core ownership: core owns workflow state machines, replay mediation, workflow cache entries, activation construction, nondeterminism detection, and eviction when cached state cannot be reused.
- Server ownership: History stores the ordered event log, task scheduling decisions, timers, activity results, signals, updates, cancellation events, and workflow-task failures. It does not rely on worker process memory for correctness.
- Deterministic contract: workflow code must produce the same command sequence for the same prior history. Activities, external I/O, random values, and wall-clock reads belong behind Temporal APIs so replay reads recorded events instead of repeating side effects.
- Failure behavior: after worker crash or eviction, replay rebuilds state before new work is processed. If replay detects a different command sequence, sdk-core treats it as nondeterminism and fails or evicts the workflow task instead of corrupting history.
- Source map: `sdk-python/temporalio/worker/_workflow.py:_handle_activation`, `sdk-core/crates/sdk-core/src/worker/workflow/mod.rs:next_workflow_activation`, `sdk-core/crates/sdk-core/src/worker/workflow/machines/workflow_machines.rs:get_wf_activation`, `sdk-core/crates/protos/src/protos/mod.rs:WorkflowActivation`, and `temporal/service/history/handler.go:RespondWorkflowTaskCompleted`.
- Try it command: `python hacks/004_history_replay.py`; look for the History, core worker, and Python activation notes and the printed replay rule.

<a id="retry-and-failure-handling"></a>
## 8. Retry and failure handling

- User-level event: an activity raises, times out, is canceled, or a workflow task fails because Python could not complete an activation. Kilvin code usually sees this as an awaited activity result, retry exhaustion, cancellation, or workflow failure.
- Temporal boundary: activity completion/failure flows from Python through bridge and sdk-core to History. Retry attempts return later as new activity tasks through Matching. Workflow-task failures flow through workflow activation completion rather than activity completion.
- sdk-core ownership: core translates Python exceptions and cancellations into completion payloads, reports workflow-task failures, keeps polling for replacement tasks, and mediates retry/cancellation state back into future activations.
- Server ownership: History records activity failure or timeout events, applies retry policy, computes backoff/timers, schedules the next activity attempt, and records final failure when retry is exhausted. Matching only dispatches ready tasks.
- Deterministic contract: workflow replay must observe the same failure and retry events in history. The activity body may run multiple times, so side effects need idempotency or external guards.
- Failure behavior: worker crash before completion leaves no successful completion recorded; timeout or retry policy decides the next step. Non-retryable failure, max attempts, cancellation, or workflow-task nondeterminism stop the retry path differently.
- Source map: `kilvin-py/kilvin_py/workflows.py:RetryPolicy`, `sdk-python/temporalio/worker/_activity.py:complete_activity_task`, `sdk-core/crates/sdk-core/src/worker/client.rs:complete_activity_task`, `temporal/service/history/workflow/mutable_state_impl.go:AddActivityTaskFailedEvent`, `temporal/service/history/workflow/mutable_state_impl.go:RetryActivity`, and `temporal/service/history/workflow/mutable_state_impl.go:AddWorkflowTaskFailedEvent`.
- Try it command: `python hacks/005_control_paths.py`; look for the Retry scenario and its details about Python failure, History retry scheduling, and Matching dispatch.

<a id="pause-resume-as-signalupdate-driven-coordination"></a>
## 9. Pause/resume as signal/update-driven coordination

- User-level event: an operator pauses or resumes a training run while the workflow is waiting on activities or timers. The workflow changes durable coordination state, not just a Python boolean in memory.
- Temporal boundary: signal or update requests enter Frontend/History and appear in workflow activations as signal or update jobs. The workflow completion returns commands that reflect the new pause state.
- sdk-core ownership: core replays the signal/update event into workflow state machines, delivers activation jobs to sdk-python, orders those jobs with any other history events, and reports the resulting commands or failure.
- Server ownership: History records the signal or update event, stores accepted update protocol messages where relevant, schedules a workflow task, and keeps the event available for replay after restarts.
- Deterministic contract: pause/resume handlers must mutate workflow state deterministically from event payloads. Queries can inspect state but must not cause durable changes; activities still perform side effects outside workflow replay.
- Failure behavior: if the worker dies after the signal/update is recorded but before completion, a later workflow task replays the same event. If the handler throws, the workflow task can fail and be retried without losing the recorded request.
- Source map: `temporal/service/history/handler.go:SignalWorkflowExecution`, `temporal/service/history/handler.go:UpdateWorkflowExecution`, `sdk-core/crates/protos/src/protos/mod.rs:SignalWorkflow`, `sdk-core/crates/sdk-core/src/worker/workflow/machines/workflow_machines.rs:SignalWorkflow`, and `sdk-python/temporalio/worker/_workflow.py:_handle_activation`.
- Try it command: `python hacks/005_control_paths.py`; look for the Pause / resume scenario and confirm it ties deterministic Python state to durable History events.

<a id="sticky-workflow-cache-and-eviction"></a>
## 10. Sticky workflow cache and eviction

- User-level event: a workflow that was warm on one worker resumes after a cache miss, worker restart, deployment change, or capacity eviction. The user-visible result should be the same as if it had stayed cached.
- Temporal boundary: workflow tasks may be routed to a sticky task queue, but a sticky miss falls back to normal task queue polling plus replay. Eviction can also be delivered to Python as a remove-from-cache activation.
- sdk-core ownership: core owns the workflow run cache, sticky slot pressure, eviction reasons, replay after cache miss, and the activation that tells sdk-python to drop cached state.
- Server ownership: History remains authoritative and can clear or bypass sticky routing when needed. Matching dispatches either sticky or normal workflow tasks; History validates the eventual completion against durable events.
- Deterministic contract: cached workflow memory is never correctness state. Replaying the same history after eviction must rebuild the same workflow decisions before any new command is accepted.
- Failure behavior: cache-full eviction, language failure, nondeterminism, task-not-found, or pagination/history fetch can remove a run from cache. Nondeterminism is treated as workflow-task failure, while ordinary cache miss just causes replay.
- Source map: `sdk-core/crates/sdk-core/src/worker/workflow/run_cache.rs:EvictionReason`, `sdk-core/crates/sdk-core/src/worker/workflow/workflow_stream.rs:CacheFull`, `sdk-core/crates/sdk-core/src/worker/workflow/managed_run.rs:create_evict_activation`, `sdk-core/crates/protos/src/protos/mod.rs:create_evict_activation`, and `temporal/service/history/workflow/mutable_state_impl.go:ClearStickyTaskQueue`.
- Try it command: `python hacks/005_control_paths.py`; look for the Sticky cache eviction scenario and connect its fallback-to-replay explanation to the cache refs above.

<a id="where-to-inspect-source-next"></a>
## 11. Where to inspect source next

Use the explorer's source refs for exact line anchors. Start with Kilvin's client and worker files, then sdk-python worker loops, bridge worker calls, sdk-core worker initialization and pollers, and Temporal server Frontend, History, and Matching handlers.

Try it: `python hacks/001_source_map.py`

<a id="hands-on-hacks"></a>
## 12. Hands-on hacks

Run `python hacks/001_source_map.py` first, then `002`, `003`, `004`, and `005`. `006_optional_local_run.py` is opt-in and should not be part of default verification.
