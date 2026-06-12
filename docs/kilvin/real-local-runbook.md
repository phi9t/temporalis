# Kilvin Real Local Runbook

This runbook is the happy path for proving the real Kilvin implementation on a laptop: Temporal workflow, local allocator, docker image build, registry, k3s Job, trainer logs, and artifacts.

## 1. Preflight

Run:

```bash
make kilvin-doctor
```

Fix `FAIL` rows before starting a live run. `WARN` rows usually mean an optional verifier such as `kubectl` or the Temporal CLI is unavailable; the smoke script can still use artifacts for required proof.

On macOS with Homebrew Colima, make sure Homebrew tools are visible:

```bash
export PATH=/opt/homebrew/bin:$PATH
```

## 2. Start Infra

```bash
cd kilvin-py
./infra/up.sh
```

This starts Temporal, Temporal UI, the allocator, registry, Postgres, and k3s.

Useful inspection points:

```bash
docker compose -f kilvin-py/infra/docker-compose.yml ps
curl -fsS http://localhost:7070/healthz
curl -fsS http://localhost:7070/v1/allocations
```

Temporal UI is available at:

```text
http://localhost:8080
```

## 3. Run The Canonical Smoke Proof

From the repo root:

```bash
make kilvin-real-smoke
```

The smoke script starts a host worker, starts one workflow, waits for completion, checks artifacts, checks trainer logs, and verifies allocator release.

The workflow result should contain:

```text
KILVIN_TRAINING_COMPLETED:<run-id>
```

## 4. Inspect A Run Manually

Artifacts live under:

```text
.kilvin-artifacts/<run-id>/1/artifacts/pretrain/
```

Important files:

```text
concretize_dependencies/out.yaml
allocate_resources/quota_decision.yaml
materialize_training_bundle/env_vars.yaml
monitor_training/logs.yaml
```

Temporal trace:

```bash
temporal workflow query -w kilvin-training-<run-id> --type run_step_trace
```

k3s jobs:

```bash
kubectl --kubeconfig kilvin-py/infra/.kubeconfig/kubeconfig.yaml -n kilvin-training get jobs,pods
```

Allocator release:

```bash
curl -fsS http://localhost:7070/v1/allocations
```

## 5. Verify Hosted Explorer Data After Publishing

After pushing explorer/generated-data changes, run:

```bash
make kilvin-pages-check
```

This checks the public `kilvin/internals.json` for the real implementation language.

## 6. Tear Down

```bash
cd kilvin-py
./infra/down.sh
```

`down.sh` removes compose volumes, so allocator state and registry contents reset.
