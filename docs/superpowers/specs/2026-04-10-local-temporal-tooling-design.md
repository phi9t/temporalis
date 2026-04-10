# Local Temporal Tooling Design

## Goal

Build a single-user local workflow tool in both Python and Go that delivers a pipeline/workflow experience with durable local execution on the same laptop, supports both blocking and daemon-backed execution modes, and preserves a path toward stronger Go distribution with a serious single-binary attempt.

## Scope

This design covers:

- A shared local-runtime architecture
- A Python implementation optimized for speed of delivery and feature leverage
- A Go implementation optimized for stronger packaging and local UX
- A unified Go investigation track for a single-binary distribution story
- A comprehensive test strategy across unit, integration, smoke, and live layers

This design does not cover:

- Multi-user or multi-host deployments
- Temporal Cloud
- Production-grade HA server operation
- Full workflow versioning rollout strategies
- Replacing Temporal with a custom workflow engine in v1

## Constraints

- Same-laptop durability is sufficient for v1
- Both blocking and daemon-backed modes must be available
- Distribution matters, especially for Go
- The implementation should follow what the repos actually support rather than relying on unsupported embedding assumptions

## Repo-Derived Conclusions

### Temporal Is Not A Pure Embedded Library

The server architecture is explicitly service-based. User code talks to the Temporal service over gRPC, and workers poll task queues from the service rather than running against an in-process orchestration runtime.

This is reflected in:

- `temporal/docs/architecture/README.md`
- `sdk-core/ARCHITECTURE.md`
- `sdk-core/TECHNICAL_DEEP_DIVE.md`

Therefore, the realistic low-infra shape is:

`local tool -> local Temporal service -> local worker`

not:

`local tool -> embedded Temporal server library`

### Python Has First-Class Local Server Bootstrapping

The Python SDK exposes `WorkflowEnvironment.start_local()` which starts a full local Temporal server via the CLI dev server using SQLite persistence.

This is the strongest repo-backed primitive for a local single-user experience and should be treated as the baseline operational model for Python.

### Cookbook Examples Validate Thin Entry Point + Workflow + Activity Split

The durable MCP server and agent recipes all follow the same pattern:

- Thin entrypoint
- Orchestration in workflow code
- External calls in activities
- Retries and heartbeats delegated to Temporal

That pattern should be preserved in both implementations.

## Shared Runtime Architecture

### Runtime Shape

Both Python and Go implementations should share the same conceptual structure:

1. CLI/API facade
2. Local runtime manager
3. Local Temporal dev server
4. Local worker
5. Workflow/activity packages

The runtime manager is the key local abstraction. It is responsible for:

- Discovering the tool state directory
- Starting or reusing the local Temporal server
- Starting or reusing the worker
- Providing liveness and readiness checks
- Exposing a narrow internal API for `run`, `submit`, `status`, `cancel`, `logs`, and `doctor`

### State Directory

Each tool should maintain a local state directory, for example:

`<tool-state-dir>/`

with at least:

- `server/`
- `worker/`
- `db/temporal.sqlite` or equivalent
- `run/` for PID or socket metadata
- `logs/`
- `config/`

### Execution Modes

Two execution modes must exist on top of the same storage and queue model.

#### Blocking Mode

- Command ensures local runtime is healthy
- Command submits a workflow
- Command waits for completion
- Progress is streamed to stdout/stderr
- Exit code reflects workflow outcome

#### Daemon-Backed Mode

- Command ensures background supervisor is healthy
- Background supervisor owns server and worker lifecycle
- Command submits workflow and returns immediately
- Follow-up commands inspect/cancel results later

### Workflow Boundaries

V1 workflows should be intentionally conservative:

- Deterministic orchestration only
- Activities own all I/O and mutation
- Heartbeats for long-running activities
- Workflow signals/queries only when they directly improve local UX

### Task Queue Strategy

Keep task queue strategy minimal:

- One default workflow queue
- One default activity queue
- Optional future specialization only when there is an actual need

Avoid over-partitioning.

## Python Design

### Primary Objective

Optimize for fastest path to a robust local workflow tool while staying close to supported SDK patterns.

### Process Model

Python should ship two entrypoints from one package:

- Main CLI
- Internal worker command

The local runtime manager should:

- Use Python SDK facilities to bootstrap the local Temporal dev server
- Connect a normal Temporal client
- Start a worker process or reuse one
- Submit workflows and track handles

### Why Python First

Python has direct leverage from:

- `WorkflowEnvironment.start_local()`
- Strong cookbook coverage for agents, tools, retries, and durable MCP flows
- `OpenAIAgentsPlugin` for durable local agent orchestration when needed

### Packaging Tradeoff

Python is not the preferred final distribution form.

It is acceptable for:

- Local development
- Rapid feature iteration
- Design validation

It is not ideal for:

- Strong single-binary distribution
- Minimal installation story

### Python Workflow Style

Use the repo-backed pattern:

- Workflow classes define orchestration
- Activities perform API calls, subprocess work, file mutation, model calls, and polling
- Long-running activities heartbeat and respond to cancellation
- Dynamic tools are allowed when building agent/tool flows

## Go Design

### Primary Objective

Build the local tool in a way that feels like one shipped product while preserving real Temporal semantics behind the scenes.

### Process Model

The Go executable should contain:

- CLI commands
- Local runtime manager
- Worker registration and startup path
- Workflow/activity packages

The local runtime manager should:

- Manage the state directory
- Ensure the local Temporal service is running
- Start or reuse a worker
- Support foreground and background lifecycles

### Distribution Story

Go is the preferred implementation for end-user distribution because:

- Static binaries are easier to ship
- Supervisor logic is straightforward
- CLI experience is stronger

The main compromise is that the actual Temporal service is still not a Go library embed in any supported form from this workspace.

### Go Workflow Style

Use ordinary Temporal workflow/activity patterns:

- Small deterministic workflows
- Retry policies at call sites where useful
- Struct-based activity grouping when dependency injection helps
- Heartbeating for long-running operations

## Unified Go Single-Binary Investigation

### Objective

Give a serious attempt at a single-binary distribution story for Go because distribution is an explicit requirement.

### What Must Be Evaluated Honestly

Based on the repo architecture, there is no supported indication that the Temporal server can be linked as an embeddable Go library.

The likely options are:

1. Bundle and supervise a local Temporal server process from the same binary
2. Package a second server artifact alongside the main Go binary and self-install it
3. Abandon actual Temporal for a narrower custom engine if true single-binary is mandatory

### Recommended Investigation Order

#### Option A: Single Binary Supervisor With Bundled Server Payload

Try to make one Go binary that:

- Contains the main CLI
- Contains or downloads the server payload on first run
- Materializes the server executable into the state directory
- Supervises it transparently

This is not true embedding, but it may satisfy distribution goals if the end-user experience is one downloaded binary.

#### Option B: Self-Installing Secondary Artifact

If embedding the server payload inside the main binary is too awkward or fragile:

- Ship one Go binary
- On first run, fetch or unpack the exact Temporal server/CLI binary
- Cache it locally
- Treat it as a managed dependency

#### Option C: Replace Temporal For The Unified Go Build

If the first two fail to meet the single-binary requirement strongly enough, evaluate a custom checkpoint runner as a separate product decision.

This is explicitly a fallback because it forfeits Temporal semantics and should not be conflated with the actual Temporal-backed local tool.

### Success Criteria For The Investigation

The unified Go attempt succeeds only if:

- The user downloads one binary
- First-run bootstrapping is automatic
- Blocking and daemon-backed modes still work
- Upgrade and restart semantics remain clear
- The implementation stays supportable

If those criteria are not met, the investigation should be marked unsuccessful rather than defended cosmetically.

## Command Surface

Both Python and Go should converge on a similar command surface:

- `run` — blocking execution
- `submit` — daemon-backed submission
- `status` — inspect current run state
- `logs` — show runtime or workflow logs
- `cancel` — request cancellation
- `doctor` — validate runtime health
- `daemon start`
- `daemon stop`
- `daemon status`

Optional later commands:

- `list`
- `resume`
- `describe`

## Failure Model

### In Scope

- Process restart on same machine
- Machine reboot with persisted local state
- Activity retries for transient failures
- Cancellation from user commands

### Out Of Scope For V1

- Cross-machine failover
- Shared multi-user queues
- Server-cluster durability beyond local SQLite-backed local state
- Zero-downtime version migration for long-lived production workflows

## Comprehensive Test Strategy

The test plan must validate behavior at multiple layers. Each implementation should use the same test taxonomy even if the exact framework differs.

### 1. Unit Tests

Purpose: verify logic without requiring a real local server.

Coverage should include:

- Runtime manager state transitions
- Config parsing and defaulting
- State directory resolution
- PID/socket/lock-file handling
- Command option parsing
- Workflow input validation
- Retry policy selection
- Error classification
- Log and progress formatting
- Supervisor decision logic for blocking vs daemon-backed execution

For workflow logic itself:

- Pure helper functions should be unit tested normally
- Activity wrapper logic should be unit tested with mocks/fakes
- Polling helpers should be tested with deterministic fake clocks where available

### 2. Integration Tests

Purpose: verify the real local runtime stack with a real Temporal-compatible local environment.

Coverage should include:

- Bootstrapping local runtime from an empty state directory
- Running a simple happy-path workflow in blocking mode
- Submitting a workflow in daemon-backed mode and retrieving status
- Server reuse across multiple CLI invocations
- Worker reuse or replacement across multiple invocations
- Long-running activity heartbeat and resume behavior
- Workflow cancellation
- Retry behavior for transient activity failures
- Persistence across process restart
- Persistence across simulated machine reboot equivalents where feasible

Python integration tests should use the SDK-backed local environment where appropriate.

Go integration tests should stand up the managed local runtime in temporary directories and run against the real local service process.

### 3. Smoke Tests

Purpose: validate packaged user-facing flows from the outside with minimal assumptions.

Coverage should include:

- Fresh install or first-run bootstrap
- `doctor`
- `run`
- `submit`
- `status`
- `cancel`
- `daemon start/stop/status`

Smoke tests should be black-box and operate on the built artifact rather than package internals.

These should verify:

- Exit codes
- Basic stdout/stderr contract
- Minimal latency expectations for startup
- State directory creation
- Recoverability after abrupt tool termination

### 4. Live Tests

Purpose: validate the real side-effecting edges that matter in production-like local usage.

Coverage should include:

- Real subprocess activity execution
- Real filesystem mutation workflows
- Real HTTP-based activities against controllable endpoints
- If agent workflows are included, real model-call paths behind explicit opt-in

Live tests should be:

- Opt-in only
- Clearly marked and segregated
- Safe to skip in CI
- Able to run against disposable local resources

### 5. Failure Injection Tests

Purpose: prove the local durability claim rather than assume it.

Coverage should include:

- Kill worker during activity execution
- Kill CLI during blocking mode
- Kill or restart local server during a recoverable window
- Retry after transient HTTP failures
- Resume after heartbeat-bearing activity interruption

This layer is critical because the entire value proposition is durable local workflow execution rather than ordinary scripting.

### 6. Packaging/Distribution Tests

Purpose: validate the distribution story separately from runtime correctness.

Coverage should include:

- Clean-machine first-run bootstrap
- Upgrade path across versions
- Cache reuse behavior
- Corrupt cache recovery
- Path relocation behavior

For the unified Go attempt, this test layer must explicitly validate whether one delivered binary is enough in practice.

## Test Structure By Implementation

### Python

Recommended structure:

- `tests/unit/`
- `tests/integration/`
- `tests/smoke/`
- `tests/live/`

Use:

- ordinary pytest for unit
- SDK-backed local environments for most integration
- subprocess-based black-box tests for smoke
- opt-in markers for live

### Go

Recommended structure:

- package-level unit tests next to source
- `integration/` for real local-runtime tests
- `smoke/` for black-box CLI tests against built artifacts
- `live/` for opt-in external-edge tests

Use:

- `go test` for unit and integration
- built binary invocation for smoke
- environment-gated tests for live

## Test Execution Levels

The project should support at least these execution levels:

- fast local developer run
- CI default
- pre-release validation

### Fast Local Developer Run

Should include:

- unit tests
- the smallest subset of integration tests

### CI Default

Should include:

- all unit tests
- deterministic integration tests
- smoke tests

### Pre-Release Validation

Should include:

- full integration suite
- smoke suite on packaged artifacts
- live tests
- failure injection tests
- unified Go packaging tests

## Acceptance Criteria

The work is successful when:

- A local user can run a workflow tool in blocking mode
- A local user can submit work in daemon-backed mode
- Work survives process restart on the same machine
- Runtime setup is automatic and local
- Python implementation validates the workflow architecture quickly
- Go implementation provides a better packaging path
- The unified Go attempt is evaluated rigorously with explicit success/failure criteria
- The test matrix proves durability, not just happy-path execution

## Risks

### Python Packaging Risk

Python can deliver the runtime model quickly, but the packaging story may remain second-class.

### Go Single-Binary Risk

The strongest distribution requirement may not be satisfiable with actual Temporal semantics in a true embedded sense.

### Local Server Lifecycle Risk

Server startup, cache corruption, and orphaned background processes can degrade UX if the runtime manager is weak.

### Testing Risk

If tests focus only on happy-path workflow execution, the project may claim durability it has not actually demonstrated.

## Recommendation

Proceed in this order:

1. Build the Python local-runtime implementation to validate the operational model quickly
2. Build the Go local-runtime implementation to establish the preferred distribution path
3. Run the unified Go single-binary investigation in parallel or immediately after the first usable Go path exists
4. Keep the fallback option of a custom checkpoint runner as a separate product decision, not an implementation shortcut
