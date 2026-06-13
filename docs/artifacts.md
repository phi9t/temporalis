# Reading Kilvin Artifacts

Kilvin writes artifacts so a training run can be explained after the fact. The
goal is not to preserve every byte of runtime output; the goal is to preserve
the evidence that matters for durable orchestration: what was requested, what
was decided, what was submitted, and what happened.

The local artifact store is filesystem-backed:

```text
.kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/
```

Every workflow step writes `in.yaml` and `out.yaml`. Some steps also write a
teaching artifact with the operator-facing evidence for that step.

## Artifact Ledger

| Step | Main files | What to read first | What it teaches |
| --- | --- | --- | --- |
| `interpret_intent` | `in.yaml`, `out.yaml` | `out.yaml` | How the researcher request became typed workflow state. |
| `concretize_dependencies` | `in.yaml`, `out.yaml` | `out.yaml` | Which image ref, image digest, and lockfile checksum define the runnable environment. |
| `allocate_resources` | `in.yaml`, `out.yaml`, `quota_decision.yaml` | `quota_decision.yaml` | Why capacity was granted and what the allocator saw before reserving resources. |
| `materialize_training_bundle` | `in.yaml`, `out.yaml`, `env_vars.yaml` | `out.yaml`, then `env_vars.yaml` | The literal Kubernetes Job shape and trainer environment that will launch. |
| `submit_k8s_job` | `in.yaml`, `out.yaml` | `out.yaml` | The Kubernetes job name, UID, and namespace used for follow-up inspection. |
| `monitor_training` | `in.yaml`, `out.yaml`, `logs.yaml` | `logs.yaml`, then `out.yaml` | The observed trainer output and final monitor status. |

## How To Read A Run

Start with intent:

```bash
sed -n '1,160p' .kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/interpret_intent/out.yaml
```

Look for:

- `component_profile.model`;
- `component_profile.dataset_root`;
- `checkpoint`;
- `image_ref`;
- `trainer_env`.

This is the boundary where the production-shaped request becomes local,
laptop-scale execution state.

Then read dependency evidence:

```bash
sed -n '1,120p' .kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/concretize_dependencies/out.yaml
```

Look for:

- `image_ref`;
- `image_digest`;
- `lockfile_sha256`.

This answers: "Which exact training environment did we materialize?" In a
larger platform, this is where CUDA, Torch, NCCL, custom kernels, and registry
compatibility become concrete evidence rather than tribal memory.

Then read quota evidence:

```bash
sed -n '1,160p' .kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/allocate_resources/quota_decision.yaml
```

Look for:

- requested vs granted CPU/memory;
- available capacity before allocation;
- cluster;
- reason.

This answers: "Why did this run get these resources?" The local allocator is
small, but the shape matches larger GPU placement systems: capacity is scarce,
placement changes over time, and the decision needs to be inspectable later.

Then read the materialized launch:

```bash
sed -n '1,220p' .kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/materialize_training_bundle/out.yaml
sed -n '1,120p' .kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/materialize_training_bundle/env_vars.yaml
```

Look for:

- `job_manifest`;
- `launch_plan`;
- `health_checks`;
- trainer env vars such as `RUN_ID`, `MODEL_NAME`, `MAX_STEPS`, `DATASET_MOUNT`,
  and `CHECKPOINT_URI`.

This answers: "What exactly did we ask Kubernetes to run?" If runtime behavior
looks wrong, compare monitor logs against this materialized spec.

Then read monitoring evidence:

```bash
sed -n '1,160p' .kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/monitor_training/logs.yaml
sed -n '1,120p' .kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/monitor_training/out.yaml
```

Look for:

- trainer log lines;
- `final_status`;
- `logs_uri`;
- pod counts.

This answers: "What actually happened after launch?" In Temporal terms, this is
why monitoring is a heartbeating activity: it can run for a long time, record
progress, and recover if the worker process disappears.

## Checksums Matter

The artifact writer stores each YAML artifact as a `StepIOArtifact` with:

- `uri`;
- `format`;
- `checksum_sha256`;
- `size_bytes`.

That makes the workflow trace content-addressable enough for teaching: when a
step envelope points to an artifact, the reader can inspect the payload and know
which exact bytes the workflow recorded.

## Debugging Questions

Use these questions when a run surprises you:

- Did `interpret_intent/out.yaml` preserve the right model, dataset, checkpoint,
  and trainer env?
- Did `concretize_dependencies/out.yaml` record an immutable image digest?
- Did `quota_decision.yaml` show enough capacity before allocation?
- Did `materialize_training_bundle/out.yaml` include the env vars and mounts the
  trainer needed?
- Did `submit_k8s_job/out.yaml` point at the job you inspected in Kubernetes?
- Did `monitor_training/logs.yaml` agree with the final monitor status?

If you can answer those from artifacts and Temporal history, the run is
explainable even when the original worker process is gone.
