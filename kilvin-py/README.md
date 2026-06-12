# kilvin-py — one training request, materialized by one Temporal workflow

One clean request — **train model X on FineWeb with 64 A100 GPUs** — and a single
`KilvinTrainingWorkflow` that turns that intent into a running job. This is the
runnable counterpart to the [explorer](../explorer/) and
[HACKERS_GUIDE.md](../HACKERS_GUIDE.md): the same story you read there executes
here against a real Temporal server, and every step leaves an inspectable YAML
artifact behind.

## The workflow

`KilvinTrainingWorkflow` (task queue `kilvin-training-task-queue`) runs six steps:

| Step | Activity | What it persists |
| --- | --- | --- |
| 1 | `interpret_training_intent` | the typed plan extracted from the run config |
| 2 | `concretize_dependencies` | the pinned code bundle (image + deps) |
| 3 | `allocate_resources` | the placement decision plus `quota_decision.yaml` |
| 4 | `materialize_training_bundle` | the concrete job spec plus `env_vars.yaml` |
| 5 | `submit_k8s_job` | the Kubernetes job id and namespace |
| 6 | `monitor_training` | heartbeats while polling, plus `logs.yaml` |

Every step also writes `in.yaml` / `out.yaml`, so a run is debuggable from disk
alone:

```
.kilvin-artifacts/{run_id}/{attempt}/artifacts/pretrain/
  interpret_intent/{in,out}.yaml
  concretize_dependencies/{in,out}.yaml
  allocate_resources/{in,out,quota_decision}.yaml
  materialize_training_bundle/{in,out,env_vars}.yaml
  submit_k8s_job/{in,out}.yaml
  monitor_training/{in,out,logs}.yaml
```

Signals: `pause`, `resume`, `pause_at_step`, `replay_step`, `cancel`.
Queries: `run_status`, `run_step_trace`, `run_artifacts`, `run_plan`.

## Run it

Three terminals (or background the first two). Requires the
[`temporal` CLI](https://docs.temporal.io/cli) and Python ≥ 3.11 with
`temporalio` (a ready `.venv` works too).

```bash
# 1. A real local Temporal server (in-memory, with Web UI on :8233)
temporal server start-dev

# 2. The worker — registers the workflow and all seven activities
cd kilvin-py
python worker.py

# 3. Submit the request
python start_workflow.py
# Result: KILVIN_TRAINING_COMPLETED:run-<id>
```

Then look under the hood:

```bash
# The durable step trace, straight from the workflow's query handler.
# If the result printed run-abc12345, the workflow id is kilvin-training-run-abc12345.
temporal workflow query -w kilvin-training-run-<id> --type run_step_trace

# The stage plan and every artifact URI
temporal workflow query -w kilvin-training-run-<id> --type run_plan
temporal workflow query -w kilvin-training-run-<id> --type run_artifacts

# The raw event history Temporal replays from (the real source of truth)
temporal workflow show -w kilvin-training-run-<id>
```

## Drive the control paths

Signals are durable history events, so they survive worker restarts — you can
even pause a run before any worker has picked it up:

```bash
# Pause a live run, watch it park, then let it finish
temporal workflow signal -w kilvin-training-run-<id> --name pause
temporal workflow query  -w kilvin-training-run-<id> --type run_status   # PAUSED
temporal workflow signal -w kilvin-training-run-<id> --name resume
```

`pause_at_step` parks the run right before a chosen step, and `replay_step`
re-executes from a step while recording SKIPPED envelopes for everything before
it — the explorer's Control Paths track shows where each of these diverges from
the happy path inside Temporal's internals.
