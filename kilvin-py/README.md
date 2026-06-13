# kilvin-py — one training request, materialized by one Temporal workflow

One clean request — **train model X on FineWeb with 64 A100 GPUs** — and a single
`KilvinTrainingWorkflow` that turns that intent into a running job. This is the
runnable counterpart to the [explorer](../explorer/) and
[HACKERS_GUIDE.md](../HACKERS_GUIDE.md): the same story you read there executes
here against a real Temporal server, and every step leaves an inspectable YAML
artifact behind.

Kilvin is intentionally not a full foundation-model platform. It is the
smallest real slice that preserves the platform shape: intent, dependency
materialization, quota, launch-spec materialization, Kubernetes submission,
monitoring, and operator control. For the larger training-system motivation, see
[Durable Model Training Systems](../docs/model-training-systems.md).

## The workflow

`KilvinTrainingWorkflow` (task queue `kilvin-training-task-queue`) runs six steps:

| Step | Activity | What it persists |
| --- | --- | --- |
| 1 | `interpret_training_intent` | the typed plan extracted from the run config |
| 2 | `concretize_dependencies` | the digest-pinned trainer image plus lockfile SHA |
| 3 | `allocate_resources` | the allocator grant plus `quota_decision.yaml` |
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

## Run it for real

Prereqs: docker (colima), kubectl, uv, python 3.10+.

1. `infra/up.sh` — brings up Temporal (+ UI at http://localhost:8080), the
   resource allocator, a local registry, and a k3s cluster, all via docker
   compose. First run downloads images; give colima >=4 CPUs / 8GB
   (`colima start --cpu 4 --memory 8`).
2. `python worker.py` — host worker; it drives `uv`, `docker build/push`, and
   the k3s kubeconfig exported to `infra/.kubeconfig/kubeconfig.yaml`.
3. `python start_workflow.py` — one training run, end to end. First run builds
   the trainer image (torch CPU wheels; a few minutes, cached afterwards).
4. Watch: Temporal UI, `kubectl --kubeconfig infra/.kubeconfig/kubeconfig.yaml
   -n kilvin-training get jobs,pods`, `curl localhost:7070/v1/allocations`,
   and `.kilvin-artifacts/<run-id>/...` (quota_decision.yaml, env_vars.yaml,
   logs.yaml with the real loss curve).
5. `infra/down.sh` — tear down (resets the ledger and registry).

The workflow id is still `kilvin-training-run-<id>`, so the same query handles
work once the run starts:

```bash
temporal workflow query -w kilvin-training-run-<id> --type run_step_trace
temporal workflow query -w kilvin-training-run-<id> --type run_plan
temporal workflow query -w kilvin-training-run-<id> --type run_artifacts
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
