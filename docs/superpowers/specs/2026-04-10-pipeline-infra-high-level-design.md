# High-Level Pipeline Infrastructure Design

## Goal

Build a Python-first, local-first pipeline framework that feels as simple as a lightweight state-threaded engine while using Temporal underneath for durability, retries, pause/resume, and execution correctness.

The user-facing surface should stay minimal:

- `@step`
- `@pipeline`
- `run(...)`
- `<pipeline-cli> ...`

The framework should make workflow and step business logic visually dominant and push Temporal boilerplate into a small, explicit adapter layer that is easy to maintain.

## Scope

This design covers:

- A Python-only v1 built on the Temporal Python SDK
- A local-first runtime that hides the local Temporal server and worker lifecycle
- A `@step` / `@pipeline` authoring model
- A pause-and-resume execution model using a single Temporal workflow per logical run
- A pipeline-operator CLI for inspection and resume
- Local JSONL session logs and state snapshots as human-friendly derived artifacts

This design does not cover:

- A non-Temporal runtime
- A multi-language API
- A generic multi-backend abstraction for Ray/Temporal/local execution in v1
- Temporal Cloud or remote-cluster-first deployment UX

## Repo-Derived Conclusions

### Temporal Already Solves The Hard Parts We Actually Need

The Temporal server and SDK architecture already provide the durability, retry handling, task orchestration, and resume semantics that the proposed framework needs. Rebuilding those in a custom checkpoint engine would duplicate complexity while weakening the migration story.

### Python Is The Right v1 Substrate

The Python SDK in this workspace already supports:

- local server bootstrapping for local-first workflows
- async-first workflow and activity ergonomics
- a workflow sandbox and replay support
- a clear split between workflow orchestration and activity side effects

That makes Python the fastest path to a framework that feels local and simple while remaining honestly Temporal-native.

### A Thin Facade Is Maintainable; A Compiled DSL Is Not

The framework should not attempt AST transforms, bytecode rewriting, or code generation per pipeline. Those approaches would make step dispatch, debugging, and Temporal compatibility harder to reason about.

Instead, the user should write real Python workflow code and real Python step functions, and the decorators should only attach metadata and route calls appropriately.

## Authoring Model

### Public API

The public API should be:

- `@step(...)`
- `@pipeline(...)`
- `run(pipeline_fn, state, ...)`
- `<pipeline-cli>`

Everything else is secondary and discoverable.

### Step Authoring

Non-transient steps are durable work units. They are authored as normal Python functions that accept a pipeline state and optionally a `StepContext`, then return a pipeline state.

Example:

```python
@step(max_attempts=3, backoff=2.0, requires=["new_commit_id"], produces=["build_id"])
def submit_compilation(state: MyState, ctx: StepContext) -> MyState:
    ctx.info("Submitting compilation", commit_id=state.new_commit_id)
    result = build_service.submit(state.new_commit_id)
    state.build_id = result.build_id
    return state
```

Transient steps are authored the same way, but marked `transient=True`. They are executed inline in workflow code and never become durable activity boundaries.

Example:

```python
@step(transient=True)
def validate_pipeline_start(state: MyState) -> MyState:
    if state.pipeline_mode is PipelineMode.COMMIT_FIRST and not state.source_commit_id:
        raise ValueError("COMMIT_FIRST requires source_commit_id")
    return state
```

### Pipeline Authoring

Pipelines are authored as `async def` functions so their control flow is native workflow code. Their bodies should read like straightforward business logic, with minimal boilerplate:

```python
@pipeline(name="commit-and-train", owner="ml-infra")
async def pipeline_main(state: MyState) -> MyState:
    state = validate_pipeline_start(state)
    if state.pipeline_mode is PipelineMode.COMMIT_FIRST:
        state = await clone_commit(state)
        state = await submit_compilation(state)
        state = await poll_build(state)
    state = await sync_code_and_upload(state)
    state = await meta_submit(state)
    return state
```

The framework should preserve this visual dominance. The orchestration code should not contain explicit activity invocation, retry wiring, checkpoint calls, or Temporal client code.

### Dispatch Semantics

The decorators should implement a small routing rule set:

- If a `@step` function is called outside workflow execution, run it directly. This keeps step bodies easy to unit test.
- If a `@step(transient=False)` function is called inside a pipeline workflow, route it to a Temporal activity invocation using the registered metadata.
- If a `@step(transient=True)` function is called inside a pipeline workflow, execute it inline as workflow code.

This gives the ergonomic surface of a lightweight pipeline engine while preserving Temporal’s actual execution model underneath.

## Runtime Architecture

### Local-First Execution

`run(...)` should provide a single-user local-first experience:

1. Ensure a local Temporal runtime is available, starting one if needed.
2. Ensure a worker is running for the framework task queue.
3. Start or reconnect to the workflow execution for the provided `run_id`.
4. Stream structured execution logs to stderr and session files.
5. Return the final state or surface a paused failure state cleanly.

The operator should not need to think in terms of “cluster startup” or “worker management” during normal use.

### One Logical Run Per Workflow

The framework should map:

- pipeline run -> one Temporal workflow execution
- durable step -> one Temporal activity call
- transient step -> inline workflow helper
- `run_id` -> workflow ID

This is the central invariance of the design. The framework should not create a new workflow execution on every resume or every step.

### Pause-And-Resume Model

When a durable step exhausts retries:

1. The activity fails after Temporal applies the configured retry policy.
2. The workflow catches that activity failure.
3. The framework records failure metadata in workflow state.
4. The workflow emits a structured failure event.
5. The workflow enters a waiting state for a resume signal.

On `run(resume=True)` or `<pipeline-cli> resume <run_id>`:

- the framework reconnects to the existing workflow execution
- sends a resume signal
- the workflow continues from the failed step boundary with the state already held in workflow memory/history

This is preferred over spawning a fresh workflow seeded from an external checkpoint because:

- one run has one canonical workflow history
- inspection stays simple
- no second durability system is required
- resume semantics remain exact

### No External Checkpoint Store In v1

The original custom store concept is unnecessary in the Temporal-backed design. Temporal is the durability layer.

The only state that should exist outside Temporal in v1 is human-oriented derived data:

- session logs
- state snapshots
- local metadata about the run environment

## State Model

### PipelineState

The framework should provide a `PipelineState` base dataclass, but it should be understood as workflow/application state, not as an external checkpoint payload owned by a separate engine.

The base fields should include:

- `run_id`
- `status`
- `failure_step`
- `failure_reason`
- `started_at`
- `updated_at`

The user subclasses it with domain fields:

```python
@dataclass
class MyPipelineState(PipelineState):
    pipeline_mode: PipelineMode | None = None
    source_commit_id: str | None = None
    new_commit_id: str | None = None
    build_id: str | None = None
    auto_job_id: str | None = None
    train_id: str | None = None
    artifact_path: str | None = None
```

The framework should not expose `completed_steps` as a primary mechanism in v1 because Temporal workflow progress and failure boundaries already provide the durable step progression story. Step skipping after a process restart is naturally handled by workflow resumption, not by a separate completed-step set.

### Serialization

State must be serializable by the configured Temporal data converter. The framework should provide a default serializer story for standard dataclasses/enums and fail early with a clear error if state is not serializable.

## Step Metadata And Guardrails

### Step Metadata

`@step` should support:

- `max_attempts`
- `backoff`
- `transient`
- `requires`
- `produces`
- `name`

For advanced use, a full retry policy object may be accepted, but the promoted `max_attempts` and `backoff` kwargs should remain the dominant path.

### Guardrails

The framework should fail early on:

- missing `return state`
- duplicate effective step names in a pipeline
- non-`async def` pipeline functions
- non-importable durable step functions
- failed `requires` validations
- non-serializable pipeline state

`produces` should be primarily documentary in v1, with optional debug-mode validation after step completion.

## Observability

### Temporal As Source Of Truth

Temporal is the source of truth for:

- workflow liveness
- retries
- activity failures
- pause/resume state
- durable execution history

### Local Session Artifacts As Debugging Convenience

Despite Temporal being authoritative, each run should also produce a self-contained local artifact:

- `runs/<run_id>/session.jsonl`
- `runs/<run_id>/meta.json`
- `runs/<run_id>/state_snapshots/<nnn>_<step>.json`

These artifacts are derived from workflow/activity events and local user logs. They are optimized for:

- grep/jq usage
- post-mortem debugging
- state diffs between steps
- a pipeline-native timeline view

They are not used for resume or correctness.

### StepContext

If a step declares a `ctx: StepContext` parameter, the framework should inject a structured logging helper containing:

- `run_id`
- `step_name`
- `attempt`
- `debug/info/warn/error` methods

Those methods should emit:

- Temporal-visible logs through workflow/activity loggers where appropriate
- local JSONL session entries for inspection

Steps that do not declare `StepContext` should not pay for it.

### Event Catalog

The framework should keep a fixed structured event catalog for local session logs:

- `run.start`
- `run.resume`
- `run.paused`
- `run.complete`
- `run.failed`
- `step.start`
- `step.success`
- `step.retry`
- `step.failed`
- `step.state_snapshot`
- `step.precondition_failed`
- `poll.attempt`
- `poll.success`
- `poll.timeout`
- `user.*`

## Polling

### poll_until

Polling remains a useful abstraction even with Temporal underneath. It should exist as a composable helper for long-running external operations such as build polling or training-job status checks.

Recommended v1 behavior:

- `poll_until(...)` is called inside a durable step activity
- it handles polling cadence, timeout, and progress logging
- it emits `poll.*` events to the local session log

For Temporal-native long waits, activity heartbeating and proper timeout sizing should be used so polling remains visible and interruptible.

## CLI And Inspection UX

The operator CLI should use a product-agnostic name. This document refers to it as `<pipeline-cli>`.

### Commands

V1 commands:

- `<pipeline-cli> list`
- `<pipeline-cli> inspect <run_id>`
- `<pipeline-cli> inspect <run_id> --step=<step>`
- `<pipeline-cli> logs <run_id>`
- `<pipeline-cli> resume <run_id>`

### Inspection Model

Inspection should merge:

- Temporal workflow status and failure metadata
- local session timeline
- local step-level state snapshots

The CLI must present pipeline concepts first, not raw Temporal internals first.

The output should answer:

- what step failed
- why it failed
- how many attempts were made
- what the state looked like before and after major boundaries
- whether the workflow is paused, running, or completed

## Module Layout

Recommended package layout:

- `decorators.py`
- `runtime.py`
- `workflow_runtime.py`
- `activity_runtime.py`
- `models.py`
- `polling.py`
- `logging.py`
- `inspection.py`
- `registry.py`
- `cli.py`

This keeps the facade, runtime bridge, observability, and inspection concerns separated cleanly.

## Testing Strategy

V1 tests should cover four layers:

1. Unit tests for step bodies called directly as plain functions.
2. Framework integration tests against a local Temporal environment.
3. Pause/resume tests ensuring a failed step can later continue in the same workflow execution.
4. Inspection/CLI tests validating timeline rendering, state snapshots, and resume affordances.

Replay and resume behavior should be tested explicitly because they are where Temporal-backed abstractions often become confusing if the framework gets too clever.

## Trade-Offs

### Benefits

- Real durability and retries come from Temporal, not a custom engine.
- Local-first UX is preserved.
- Workflow and step business logic remain visually prominent.
- Migration to a fuller Temporal deployment is mostly operational, not conceptual.

### Costs

- Workflow code must still respect Temporal workflow constraints.
- The framework cannot honestly support arbitrary side effects in transient workflow-side helpers.
- Local session logs become a convenience layer that must stay consistent with Temporal state, even though they are not authoritative.

## Explicit Defaults

- V1 is Python-only.
- V1 uses the Temporal Python SDK.
- V1 is local-first and hides the local runtime as much as possible.
- Durable steps execute as Temporal activities.
- Transient steps execute inline in workflow code.
- One logical run maps to one Temporal workflow execution.
- Resume works by signaling the paused workflow, not by spawning a new workflow seeded from external checkpoints.
- The operator CLI remains product-agnostic in this design (`<pipeline-cli>`).
