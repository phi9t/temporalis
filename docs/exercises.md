# Exercises

These exercises turn the explorer, generated manifests, hacks, and Kilvin
runtime into a hands-on learning path. Start with the lightweight labs; they use
checked-in data and do not require Docker, k3s, cloud credentials, or a live
Temporal server. Use the optional runtime labs when you want to prove the same
ideas against the local Kilvin stack.

## Lightweight Labs

Run the quickstart gate first:

```bash
make quickstart
```

### Lab 1: Trace Source-Grounded Internals

Goal: prove that the explorer is not just prose.

Run:

```bash
python3 hacks/001_source_map.py
```

Observe:

- refs for Temporal server, SDK Core, SDK Python, Temporal UI, and Kilvin;
- line numbers attached to lifecycle nodes;
- the same source refs surfaced in Deep Dive.

You should be able to explain why source grounding matters for learning
Temporal internals: claims about workflow start, polling, activations,
heartbeats, replay, and UI inspection should point at code.

### Lab 2: Walk One Lifecycle

Goal: see one training request move through Temporal.

Run:

```bash
python3 hacks/002_lifecycle_manifest.py
```

Then open the explorer and compare the printed phase order with
**Deep Dive / Lifecycle**.

Observe:

- the client starts the workflow;
- server history records the run;
- matching routes work to polling workers;
- SDK Core and SDK Python bridge the activation into workflow/activity code;
- completions return commands and results to Temporal.

You should be able to explain where Temporal stops making decisions and where
Kilvin activity code begins doing side effects.

### Lab 3: Inspect Task Queue Polling

Goal: understand why workers, not workflows, own execution capacity.

Run:

```bash
python3 hacks/003_task_queue_polling.py
```

Observe:

- the Matching service, SDK Core worker, Python bridge, and Python worker nodes;
- source refs for the polling path;
- how task queues decouple the training run from a specific process.

Connect it to model training: build workers, launch workers, and monitoring
workers can carry different tools and credentials while Temporal keeps the run
state durable.

### Lab 4: Explain History And Replay

Goal: separate deterministic decisions from retryable side effects.

Run:

```bash
python3 hacks/004_history_replay.py
```

Observe:

- history is the source of truth;
- workflow code can replay deterministically;
- completed activity side effects are not blindly re-executed during replay.

Connect it to training: if a worker dies after dependency concretization or
quota allocation, the workflow should recover from recorded history instead of
forgetting what already happened.

### Lab 5: Compare Control Paths

Goal: understand failure and operator-control behavior.

Run:

```bash
python3 hacks/005_control_paths.py
```

Then inspect **Deep Dive / Control Paths**.

Observe:

- retry paths for failed activities;
- pause/resume as durable signal-driven control;
- heartbeat and cancellation behavior for long-running monitoring;
- sticky replay as an optimization that still preserves correctness.

Connect it to training: retries, cancellation, monitoring recovery, and
operator hotfixes are normal platform operations, not exceptional edge cases.

## Optional Runtime Labs

These labs require Docker/Colima, k3s, a local registry, a live Temporal server,
and the Kilvin Python worker.

Start with:

```bash
make kilvin-doctor
kilvin-py/infra/up.sh
make runtime-proof
```

### Lab 6: Inspect Materialized Artifacts

Goal: verify that intent becomes evidence on disk.

Inspect:

```bash
.kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/
```

Look for:

- `interpret_intent/out.yaml`;
- `concretize_dependencies/out.yaml`;
- `allocate_resources/quota_decision.yaml`;
- `materialize_training_bundle/env_vars.yaml`;
- `monitor_training/logs.yaml`.

You should be able to explain how each artifact helps debug a failed or
surprising training run.

### Lab 7: Watch Monitoring Recoverability

Goal: connect long-running training monitors to Temporal heartbeats.

Inspect:

```bash
temporal workflow show -w kilvin-training-run-<id>
temporal workflow query -w kilvin-training-run-<id> --type run_step_trace
```

Compare Temporal history with `monitor_training/logs.yaml`.

You should be able to explain why monitoring is an activity, why it heartbeats,
and how Temporal can recover if the worker process disappears while the job is
still running.

### Lab 8: Practice Operator Control

Goal: see signals as auditable control-plane events.

Try a small run and send:

```bash
temporal workflow signal -w kilvin-training-run-<id> --name pause
temporal workflow query  -w kilvin-training-run-<id> --type run_status
temporal workflow signal -w kilvin-training-run-<id> --name resume
```

You should be able to explain why pause/resume belongs in workflow history
rather than in a side database or a process-local flag.

## Final Check

After the labs, answer these without looking:

- Which parts of Kilvin are workflow decisions?
- Which parts are activity side effects?
- What evidence proves dependencies, quota, launch spec, and monitor output?
- Which Temporal mechanism makes a long-running monitor recoverable?
- Why does a larger training platform need the same shape even when Kilvin stays
  intentionally small?
