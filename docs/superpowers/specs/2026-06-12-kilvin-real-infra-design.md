# Kilvin Real-Infra Design: uv+docker concretization, allocator service, k3s job submission, full compose plane

Status: approved 2026-06-12 (brainstormed section-by-section). Supersedes the simulated activity behavior described in the v0 design; the workflow shape (one `KilvinTrainingWorkflow`, six steps, durable step envelope) is unchanged.

## Goal

Make the kilvin-py demo as real as possible while staying laptop-scale:

- `concretize_dependencies` really pins dependencies with `uv` and really builds + pushes a docker image.
- `allocate_resources` really negotiates with a resource-allocator service holding a finite CPU ledger.
- `submit_k8s_job` really creates a Kubernetes Job; `monitor_training` really watches it.
- The training job runs one trainer image: CPU-only, tiny GPT-2-style model (PyTorch, char-level, ~0.5M params).
- The whole control plane — Temporal server, allocator, image registry, and Kubernetes itself (k3s) — is one docker compose stack.
- The term "ream" is removed from the codebase.

## Decisions (with rationale)

| Decision | Choice |
|---|---|
| Tests vs real side effects | **Real-only activities.** Workflow tests use fake activity implementations (same registered names); pure unit tests cover helpers. No simulation branches ship in `activities.py`. |
| Trainer stack | **PyTorch-only minGPT**: torch CPU wheels + numpy + pyyaml, single `trainer.py`, bundled tiny-shakespeare corpus, no runtime downloads. |
| Allocator semantics | **Finite CPU ledger** seeded from a static inventory; 409 on exhaustion so Temporal's retry policy is exercised by real contention. |
| Image delivery | **Local registry (`registry:2`) in compose**; digest-pinned image references; cluster pulls through a containerd mirror. |
| Kubernetes | **k3s server as a compose service** (kind resists compose management; k3s is designed for it). No kind binary needed. |
| Worker placement | **Host process** (kilvin-py venv): the worker is the thing that must drive `uv`, `docker`, and the kubeconfig — no docker-in-docker fragility. |
| Narrative | **Two-scale framing**: Basics keeps the production-shaped motivation (64 A100s, FineWeb) and states once that this repo materializes the same workflow for real at laptop scale. |

## Topology

```
docker compose (kilvin-py/infra/docker-compose.yml)
  postgresql ── temporal (temporalio/auto-setup, :7233) ── temporal-ui (:8080)
  resource-allocator (FastAPI, :7070, finite CPU ledger)
  registry:2 (:5001)
  k3s server (rancher/k3s, privileged, :6443; kubeconfig exported to gitignored mount;
              registries.yaml mirror: localhost:5001 -> http://registry:5000)

host: kilvin-py venv runs worker.py + start_workflow.py (unchanged roles/anchors)
      activities drive: uv, docker build/push, allocator HTTP, kubernetes client
```

`infra/up.sh`: start docker (colima) if needed → `docker compose up -d --wait` → wait for kubeconfig + node Ready → create `kilvin-training` namespace. `infra/down.sh`: `docker compose down -v`.

## New components

### `kilvin-py/infra/allocator/`

FastAPI + uvicorn, own Dockerfile (uv-based install). In-memory ledger seeded from `inventory.yaml` (cluster `local-k3s`, e.g. 8 CPUs / 16 GB).

- `POST /v1/allocations` `{run_id, stage_id, cpus, memory_gb}` → `200 {allocation_id, cluster, cpus_granted, memory_gb_granted, quota_decision{…}}`, or `409 {reason}` when the pool is exhausted.
- `DELETE /v1/allocations/{id}` releases capacity.
- `GET /v1/allocations` lists live allocations (leak visibility).
- `GET /healthz`.

### `kilvin-py/infra/k3s/registries.yaml`

containerd mirror config: image references named `localhost:5001/...` are pulled via `http://registry:5000` on the compose network.

### `kilvin-py/trainer/`

The project `concretize_dependencies` really builds:

- `pyproject.toml` + checked-in `uv.lock`: torch (CPU), numpy, pyyaml.
- `trainer.py`: char-level GPT-2-style model (causal self-attention blocks, LayerNorm, learned positional embeddings, ~0.5M params). **All hyperparameters come from env vars**, so the workflow's `env_vars.yaml` artifact is the job's literal contract. Trains a fixed number of CPU steps on the bundled corpus (`data/input.txt`), logs loss lines, writes `metrics.json` + checkpoint, exits 0/1.
- `Dockerfile`: multi-stage; `uv sync --frozen` into a venv layer (uv cache mount) → slim runtime layer.

## Activity rewrites (six step names, order, and generator anchor lines preserved)

- `interpret_training_intent`: typed plan derives trainer hyperparameters, corpus pointer, requested resources (e.g. 2 CPUs / 4 GB), and image name `localhost:5001/kilvin-trainer:<run_id>`.
- `concretize_dependencies`: `uv lock --check` in `trainer/` → `docker build` → `docker push` (async subprocesses, heartbeat per phase) → returns image ref, **digest**, lockfile SHA.
- `allocate_resources`: httpx POST to the allocator; 409 → retryable `ApplicationError("quota exhausted: …")` so the step's Temporal retry policy is the real backoff loop. Returns `ResourceAllocationOutput` (renamed from `ReamAllocationOutput`; fields made honest: cpus/memory, no fabricated GPU racks/RDMA).
- `materialize_training_bundle`: renders the actual k8s Job manifest — digest-pinned image, env vars, CPU/memory requests from the allocation, `restartPolicy: Never`, `backoffLimit: 0` (Temporal owns retries, not the kubelet). Manifest rendering is a pure, unit-testable function.
- `submit_k8s_job`: official `kubernetes` Python client + exported kubeconfig; `create_namespaced_job` in `kilvin-training`.
- `monitor_training`: polls Job conditions + pod log tail with heartbeats; persists real `logs.yaml` before the failure check (existing behavior); releases the allocation (`DELETE`) on completion and failure paths.
- `persist_yaml_artifact` unchanged. The workflow envelope — pause/resume/pause_at_step/replay/cancel signals and the four queries — is unchanged.

## Error handling

- Allocator 409 → retryable; the allocation step gets more attempts / longer backoff than the default policy.
- Build/push failure → retryable error carrying the last ~40 subprocess log lines; activity heartbeat timeout catches hung builds.
- Pod failure or image pull error → monitor returns FAILED + real log tail → stage raises with the pod's actual last words.
- Infra absent (no kubeconfig, allocator unreachable, registry refused) → **non-retryable** `ApplicationError` with a "run kilvin-py/infra/up.sh" hint: fail fast and legible.
- Orphaned allocations: visible via `GET /v1/allocations`; released on both completion and failure; `down.sh -v` resets state.

## Dependencies added

- kilvin-py worker venv: `httpx`, `kubernetes`.
- Allocator service (own pyproject): `fastapi`, `uvicorn`.
- Trainer (own pyproject): `torch` (CPU), `numpy`, `pyyaml`.

## Narrative and story surfaces

Two-scale framing: Basics keeps the 64-A100/FineWeb motivation and states once that the repo materializes the same workflow for real at laptop scale (tiny GPT-2, CPU quota from a local allocator, k3s-in-compose). Deep Dive → Kilvin Internals and HACKERS_GUIDE §3/§6 describe the real implementation (uv lock/sync, docker build+push digest, allocator HTTP ledger, k3s Job). The authored content in `explorer/scripts/build_lifecycle_data.py` (`kilvin_internals`, node/call notes) is updated and `kilvin/internals.json` regenerated. `kilvin-py/README.md` gains the real run instructions (`up.sh` → worker → start_workflow → Temporal UI → `down.sh`) and colima sizing guidance.

## Testing and verification

**Tier 1 — no infra, CI-safe (must stay green):**
- Workflow orchestration tests run in the time-skipping environment with fake activity implementations registered under the real names — pause/replay/cancel/trace coverage preserved.
- Pure unit tests: Job-manifest rendering, trainer-config derivation, allocator-client 409 mapping.
- Allocator service: FastAPI TestClient tests (grant → exhaust → 409 → release).
- Existing generator pytest suite, vitest, and explorer build.

**Tier 2 — live gate (the point of the work):**
- `infra/up.sh`; compose healthy (allocator `/healthz`, temporal-ui :8080, k3s node Ready).
- `python worker.py` + `python start_workflow.py`; assert: `KILVIN_TRAINING_COMPLETED:<run_id>`; six steps SUCCEEDED via `run_step_trace`; a real sha256 digest in the concretize `out.yaml`; allocator grant→release observed; `kubectl get job -n kilvin-training` Complete; `logs.yaml` contains real decreasing loss lines; the run visible in the Temporal Web UI.
- One control-path proof: pause-before-worker → resume → completes.

**Aesthetic assessment:** screenshots of Basics and Deep Dive → Kilvin Internals at 1440/390 (copy fits, rail/detail balance, no overflow); terminology consistency sweep (uv sync / digest / k3s / allocator) across Basics, Internals, Guide; reduced-motion re-check; live site serves the updated `internals.json`.
