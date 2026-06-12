# Kilvin Real-Infra Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the kilvin-py demo real: `concretize_dependencies` runs real `uv lock` + `docker build/push`, `allocate_resources` negotiates with a finite-ledger allocator service, `submit_k8s_job`/`monitor_training` drive a real k3s Job running a tiny CPU GPT-2 trainer — with Temporal, the allocator, a registry, and k3s all in one docker compose stack, and the term "ream" removed.

**Architecture:** Compose holds the control plane (postgresql + temporal auto-setup + temporal-ui + FastAPI allocator + registry:2 + k3s). The Temporal worker stays a host process (kilvin-py venv) because it drives host tools: `uv`, `docker`, and the exported kubeconfig. Activities are real-only; pytest covers orchestration with fake activities and pure helpers with unit tests; the live gate is a real end-to-end run. Spec: `docs/superpowers/specs/2026-06-12-kilvin-real-infra-design.md`.

**Tech Stack:** Temporal (temporalio python SDK 1.28, auto-setup server image), FastAPI + uvicorn, httpx, kubernetes python client, k3s (rancher/k3s), registry:2, uv, PyTorch CPU.

**Conventions for every task:**
- Repo root: `/Users/bytedance/workspace/temporalis`. Test command: `uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/ -q` (httpx/fastapi added for the new tests; `kubernetes` is imported lazily so tests never need it).
- Do NOT touch `tests/test_cli.py`, `tests/test_validation.py`, `tests/test_workspace.py` (parallel monoctl work, not ours).
- Generator anchors that must survive: `^\s*\w+\s*=\s*await client\.execute_workflow\(` in start_workflow.py; `Worker(` in worker.py; `^async def allocate_resources\(` and `^async def monitor_training\(` in activities.py; `step_name="<step>",` lines in workflows.py; `<a id>` anchors in HACKERS_GUIDE.md.
- Commit after every task with the message given; end commit messages with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Trainer project (`kilvin-py/trainer/`)

**Files:**
- Create: `kilvin-py/trainer/pyproject.toml`
- Create: `kilvin-py/trainer/trainer.py`
- Create: `kilvin-py/trainer/Dockerfile`
- Create: `kilvin-py/trainer/.dockerignore`
- Create: `kilvin-py/trainer/data/input.txt` (fetched)
- Create: `kilvin-py/trainer/uv.lock` (generated)

- [ ] **Step 1: Write `pyproject.toml`** (torch pinned to the CPU index via uv's documented index feature)

```toml
[project]
name = "kilvin-trainer"
version = "0.1.0"
description = "Tiny CPU GPT-2-style trainer: the image kilvin's concretize_dependencies really builds."
requires-python = ">=3.12"
dependencies = [
    "torch>=2.4",
    "numpy>=1.26",
    "pyyaml>=6.0",
]

[tool.uv.sources]
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
```

- [ ] **Step 2: Fetch the corpus** (public tiny-shakespeare, truncated to 64 KB)

```bash
mkdir -p kilvin-py/trainer/data
curl -fsSL https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt | head -c 65536 > kilvin-py/trainer/data/input.txt
wc -c kilvin-py/trainer/data/input.txt   # expect 65536
```

- [ ] **Step 3: Write `trainer.py`** — every hyperparameter comes from env vars (env_vars.yaml is the job's literal contract)

```python
"""Tiny char-level GPT-2-style trainer. CPU-only, configured entirely by env vars."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


def env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


class CausalSelfAttention(nn.Module):
    def __init__(self, n_embd: int, n_head: int) -> None:
        super().__init__()
        self.n_head = n_head
        self.qkv = nn.Linear(n_embd, 3 * n_embd)
        self.proj = nn.Linear(n_embd, n_embd)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, c = x.shape
        q, k, v = self.qkv(x).split(c, dim=2)
        q = q.view(b, t, self.n_head, c // self.n_head).transpose(1, 2)
        k = k.view(b, t, self.n_head, c // self.n_head).transpose(1, 2)
        v = v.view(b, t, self.n_head, c // self.n_head).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        return self.proj(y.transpose(1, 2).contiguous().view(b, t, c))


class Block(nn.Module):
    def __init__(self, n_embd: int, n_head: int) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn = CausalSelfAttention(n_embd, n_head)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(n_embd, 4 * n_embd), nn.GELU(), nn.Linear(4 * n_embd, n_embd)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        return x + self.mlp(self.ln2(x))


class TinyGPT(nn.Module):
    def __init__(self, vocab_size: int, n_layer: int, n_head: int, n_embd: int, block_size: int) -> None:
        super().__init__()
        self.block_size = block_size
        self.tok_emb = nn.Embedding(vocab_size, n_embd)
        self.pos_emb = nn.Embedding(block_size, n_embd)
        self.blocks = nn.ModuleList(Block(n_embd, n_head) for _ in range(n_layer))
        self.ln_f = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab_size, bias=False)

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        b, t = idx.shape
        pos = torch.arange(t, device=idx.device)
        x = self.tok_emb(idx) + self.pos_emb(pos)
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


def main() -> int:
    run_id = env_str("RUN_ID", "local")
    data_path = Path(env_str("DATA_PATH", "data/input.txt"))
    out_dir = Path(env_str("OUT_DIR", "out"))
    n_layer = env_int("N_LAYER", 4)
    n_head = env_int("N_HEAD", 4)
    n_embd = env_int("N_EMBD", 128)
    block_size = env_int("BLOCK_SIZE", 128)
    batch_size = env_int("BATCH_SIZE", 8)
    max_steps = env_int("MAX_STEPS", 200)
    lr = env_float("LEARNING_RATE", 3e-4)
    log_every = env_int("LOG_EVERY", 10)
    torch.manual_seed(env_int("SEED", 1337))

    text = data_path.read_text(encoding="utf-8")
    chars = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    data = torch.tensor([stoi[ch] for ch in text], dtype=torch.long)

    model = TinyGPT(len(chars), n_layer, n_head, n_embd, block_size)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"run_id={run_id} vocab={len(chars)} params={n_params}", flush=True)

    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    first_loss, final_loss = 0.0, 0.0
    start = time.time()
    for step in range(1, max_steps + 1):
        ix = torch.randint(len(data) - block_size - 1, (batch_size,))
        xb = torch.stack([data[i : i + block_size] for i in ix])
        yb = torch.stack([data[i + 1 : i + block_size + 1] for i in ix])
        logits = model(xb)
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), yb.view(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        final_loss = loss.item()
        if step == 1:
            first_loss = final_loss
        if step % log_every == 0 or step == 1 or step == max_steps:
            print(f"step={step} loss={final_loss:.4f}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "checkpoint.pt")
    (out_dir / "metrics.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "steps": max_steps,
                "first_loss": round(first_loss, 4),
                "final_loss": round(final_loss, 4),
                "params": n_params,
                "vocab_size": len(chars),
                "seconds": round(time.time() - start, 2),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"TRAINING_DONE run_id={run_id} final_loss={final_loss:.4f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `Dockerfile` + `.dockerignore`**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project --no-dev
COPY trainer.py ./
COPY data ./data

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["python", "trainer.py"]
```

`.dockerignore`:

```
out/
__pycache__/
```

- [ ] **Step 5: Generate and commit the lockfile, then prove a tiny host run works**

```bash
cd kilvin-py/trainer && uv lock && uv sync --frozen
MAX_STEPS=5 N_LAYER=2 N_EMBD=64 BLOCK_SIZE=64 OUT_DIR=/tmp/kilvin-trainer-out uv run python trainer.py
cat /tmp/kilvin-trainer-out/metrics.json
```

Expected: `step=1 loss=…` lines, `TRAINING_DONE`, metrics.json with first/final loss. (The local `.venv` created by `uv sync` is throwaway; ensure `kilvin-py/.gitignore` covers `trainer/.venv/` in Step 6.)

- [ ] **Step 6: Append to `kilvin-py/.gitignore`** (currently contains `.kilvin-artifacts/`)

```
trainer/.venv/
trainer/out/
infra/.kubeconfig/
```

- [ ] **Step 7: Commit**

```bash
git add kilvin-py/trainer kilvin-py/.gitignore
git commit -m "Add the real CPU GPT-2 trainer project that concretize_dependencies builds"
```

---

### Task 2: Allocator service (`kilvin-py/infra/allocator/`)

**Files:**
- Create: `kilvin-py/infra/allocator/ledger.py`
- Create: `kilvin-py/infra/allocator/app.py`
- Create: `kilvin-py/infra/allocator/inventory.yaml`
- Create: `kilvin-py/infra/allocator/pyproject.toml`
- Create: `kilvin-py/infra/allocator/Dockerfile`
- Test: `tests/infra/test_allocator.py`

- [ ] **Step 1: Write the failing tests** (`tests/infra/test_allocator.py`; ledger tests are dependency-free, app tests `importorskip` fastapi)

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kilvin-py" / "infra" / "allocator"))

from ledger import CapacityError, ClusterInventory, Ledger  # noqa: E402


def make_ledger() -> Ledger:
    return Ledger(ClusterInventory(name="local-k3s", cpus=4, memory_gb=8))


def test_ledger_grants_and_tracks_capacity() -> None:
    ledger = make_ledger()
    grant = ledger.allocate(run_id="run-a", stage_id="pretrain", cpus=2, memory_gb=4)

    assert grant.cluster == "local-k3s"
    assert grant.cpus_granted == 2
    assert grant.allocation_id
    assert grant.quota_decision["cpus_available_before"] == 4
    assert ledger.available() == (2, 4)


def test_ledger_rejects_when_exhausted_and_releases() -> None:
    ledger = make_ledger()
    grant = ledger.allocate(run_id="run-a", stage_id="pretrain", cpus=4, memory_gb=4)

    with pytest.raises(CapacityError, match="cpus"):
        ledger.allocate(run_id="run-b", stage_id="pretrain", cpus=1, memory_gb=1)

    assert ledger.release(grant.allocation_id) is True
    assert ledger.release(grant.allocation_id) is False
    assert ledger.available() == (4, 8)


def test_app_grant_exhaust_409_release_cycle() -> None:
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    from app import create_app

    app = create_app(ClusterInventory(name="local-k3s", cpus=2, memory_gb=4))
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200

    granted = client.post(
        "/v1/allocations",
        json={"run_id": "run-a", "stage_id": "pretrain", "cpus": 2, "memory_gb": 4},
    )
    assert granted.status_code == 200
    body = granted.json()
    assert body["cluster"] == "local-k3s"
    assert body["quota_decision"]["reason"]

    rejected = client.post(
        "/v1/allocations",
        json={"run_id": "run-b", "stage_id": "pretrain", "cpus": 1, "memory_gb": 1},
    )
    assert rejected.status_code == 409
    assert "exhausted" in rejected.json()["detail"]

    listing = client.get("/v1/allocations").json()
    assert len(listing["allocations"]) == 1

    released = client.delete(f"/v1/allocations/{body['allocation_id']}")
    assert released.status_code == 200
    assert client.get("/v1/allocations").json()["allocations"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/infra/ -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ledger'`

- [ ] **Step 3: Write `ledger.py`**

```python
"""Finite CPU/memory ledger for one local cluster. In-memory; reset on restart."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


class CapacityError(Exception):
    """Raised when the requested resources exceed what remains in the pool."""


@dataclass(frozen=True)
class ClusterInventory:
    name: str
    cpus: int
    memory_gb: int


@dataclass(frozen=True)
class Allocation:
    allocation_id: str
    run_id: str
    stage_id: str
    cluster: str
    cpus_granted: int
    memory_gb_granted: int
    quota_decision: dict


@dataclass
class Ledger:
    inventory: ClusterInventory
    _live: dict[str, Allocation] = field(default_factory=dict)

    def available(self) -> tuple[int, int]:
        used_cpus = sum(a.cpus_granted for a in self._live.values())
        used_mem = sum(a.memory_gb_granted for a in self._live.values())
        return self.inventory.cpus - used_cpus, self.inventory.memory_gb - used_mem

    def allocate(self, *, run_id: str, stage_id: str, cpus: int, memory_gb: int) -> Allocation:
        free_cpus, free_mem = self.available()
        if cpus > free_cpus:
            raise CapacityError(
                f"quota exhausted on {self.inventory.name}: requested {cpus} cpus, {free_cpus} free"
            )
        if memory_gb > free_mem:
            raise CapacityError(
                f"quota exhausted on {self.inventory.name}: requested {memory_gb}GB, {free_mem}GB free"
            )
        allocation = Allocation(
            allocation_id=f"alloc-{uuid.uuid4().hex[:10]}",
            run_id=run_id,
            stage_id=stage_id,
            cluster=self.inventory.name,
            cpus_granted=cpus,
            memory_gb_granted=memory_gb,
            quota_decision={
                "cluster": self.inventory.name,
                "cpus_requested": cpus,
                "cpus_granted": cpus,
                "memory_gb_requested": memory_gb,
                "memory_gb_granted": memory_gb,
                "cpus_available_before": free_cpus,
                "memory_gb_available_before": free_mem,
                "reason": (
                    f"{cpus} cpus / {memory_gb}GB fit on {self.inventory.name} "
                    f"({free_cpus} cpus, {free_mem}GB free at decision time)"
                ),
            },
        )
        self._live[allocation.allocation_id] = allocation
        return allocation

    def release(self, allocation_id: str) -> bool:
        return self._live.pop(allocation_id, None) is not None

    def live(self) -> list[Allocation]:
        return list(self._live.values())
```

- [ ] **Step 4: Write `app.py`**

```python
"""FastAPI resource allocator: a finite CPU/memory ledger over HTTP."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ledger import CapacityError, ClusterInventory, Ledger


class AllocationRequest(BaseModel):
    run_id: str
    stage_id: str
    cpus: int
    memory_gb: int


def load_inventory(path: Path) -> ClusterInventory:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ClusterInventory(name=raw["name"], cpus=int(raw["cpus"]), memory_gb=int(raw["memory_gb"]))


def create_app(inventory: ClusterInventory) -> FastAPI:
    app = FastAPI(title="kilvin-resource-allocator")
    ledger = Ledger(inventory)

    @app.get("/healthz")
    def healthz() -> dict:
        free_cpus, free_mem = ledger.available()
        return {"status": "ok", "cluster": inventory.name, "free_cpus": free_cpus, "free_memory_gb": free_mem}

    @app.post("/v1/allocations")
    def allocate(request: AllocationRequest) -> dict:
        try:
            allocation = ledger.allocate(
                run_id=request.run_id,
                stage_id=request.stage_id,
                cpus=request.cpus,
                memory_gb=request.memory_gb,
            )
        except CapacityError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        return asdict(allocation)

    @app.delete("/v1/allocations/{allocation_id}")
    def release(allocation_id: str) -> dict:
        if not ledger.release(allocation_id):
            raise HTTPException(status_code=404, detail=f"unknown allocation {allocation_id}")
        return {"released": allocation_id}

    @app.get("/v1/allocations")
    def live() -> dict:
        return {"allocations": [asdict(a) for a in ledger.live()]}

    return app


inventory_path = Path(os.environ.get("INVENTORY_PATH", Path(__file__).parent / "inventory.yaml"))
app = create_app(load_inventory(inventory_path))
```

- [ ] **Step 5: Write `inventory.yaml`, `pyproject.toml`, `Dockerfile`**

`inventory.yaml`:

```yaml
name: local-k3s
cpus: 8
memory_gb: 16
```

`pyproject.toml`:

```toml
[project]
name = "kilvin-allocator"
version = "0.1.0"
description = "Finite-ledger resource allocator for the kilvin demo."
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "pyyaml>=6.0",
]
```

`Dockerfile` (generate `uv.lock` first: `cd kilvin-py/infra/allocator && uv lock`):

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project --no-dev
COPY ledger.py app.py inventory.yaml ./
EXPOSE 7070
CMD ["/app/.venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7070"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/infra/ -q`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add kilvin-py/infra/allocator tests/infra
git commit -m "Add the finite-ledger resource allocator service"
```

---

### Task 3: Compose stack + k3s wiring + up/down scripts

**Files:**
- Create: `kilvin-py/infra/docker-compose.yml`
- Create: `kilvin-py/infra/k3s/registries.yaml`
- Create: `kilvin-py/infra/up.sh`, `kilvin-py/infra/down.sh` (chmod +x)

- [ ] **Step 1: Write `k3s/registries.yaml`** (cluster resolves `localhost:5001` image names through the compose registry)

```yaml
mirrors:
  "localhost:5001":
    endpoint:
      - "http://registry:5000"
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
name: kilvin-infra

services:
  postgresql:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U temporal"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - pgdata:/var/lib/postgresql/data

  temporal:
    image: temporalio/auto-setup:1.28.0
    depends_on:
      postgresql:
        condition: service_healthy
    environment:
      DB: postgres12
      DB_PORT: "5432"
      POSTGRES_USER: temporal
      POSTGRES_PWD: temporal
      POSTGRES_SEEDS: postgresql
    ports:
      - "7233:7233"

  temporal-ui:
    image: temporalio/ui:2.34.0
    depends_on:
      - temporal
    environment:
      TEMPORAL_ADDRESS: temporal:7233
      TEMPORAL_CORS_ORIGINS: http://localhost:3000
    ports:
      - "8080:8080"

  allocator:
    build: ./allocator
    ports:
      - "7070:7070"
    healthcheck:
      test: ["CMD", "/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:7070/healthz')"]
      interval: 5s
      timeout: 3s
      retries: 20

  registry:
    image: registry:2
    ports:
      - "5001:5000"
    volumes:
      - registry-data:/var/lib/registry

  k3s:
    image: rancher/k3s:v1.31.5-k3s1
    command: server --disable traefik --disable servicelb --disable metrics-server
    privileged: true
    environment:
      K3S_TOKEN: kilvin-local
      K3S_KUBECONFIG_OUTPUT: /output/kubeconfig.yaml
      K3S_KUBECONFIG_MODE: "666"
    volumes:
      - ./.kubeconfig:/output
      - ./k3s/registries.yaml:/etc/rancher/k3s/registries.yaml:ro
      - k3s-server:/var/lib/rancher/k3s
    ports:
      - "6443:6443"

volumes:
  pgdata:
  registry-data:
  k3s-server:
```

Image-tag note: `temporalio/auto-setup:1.28.0`, `temporalio/ui:2.34.0`, `rancher/k3s:v1.31.5-k3s1` are best-known pins — at execution, `docker pull` each; if a tag is missing pick the nearest available patch tag and record it in the compose file.

- [ ] **Step 3: Write `up.sh`**

```bash
#!/usr/bin/env bash
# Bring up the kilvin control plane: temporal + allocator + registry + k3s.
set -euo pipefail
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not running; starting colima (cpu 4, memory 8)"
  colima start --cpu 4 --memory 8
fi

mkdir -p .kubeconfig
docker compose up -d --build

echo -n "waiting for temporal :7233 "
for _ in $(seq 1 60); do nc -z localhost 7233 && break; echo -n .; sleep 2; done; echo
nc -z localhost 7233

echo -n "waiting for allocator /healthz "
for _ in $(seq 1 30); do curl -fsS localhost:7070/healthz >/dev/null 2>&1 && break; echo -n .; sleep 2; done; echo
curl -fsS localhost:7070/healthz >/dev/null

export KUBECONFIG="$PWD/.kubeconfig/kubeconfig.yaml"
echo -n "waiting for k3s node Ready "
for _ in $(seq 1 60); do
  [ -f "$KUBECONFIG" ] && kubectl get nodes 2>/dev/null | grep -q ' Ready ' && break
  echo -n .; sleep 2
done; echo
kubectl get nodes | grep -q ' Ready '

kubectl create namespace kilvin-training --dry-run=client -o yaml | kubectl apply -f -
echo "kilvin infra up:"
echo "  temporal grpc  localhost:7233   ui http://localhost:8080"
echo "  allocator      http://localhost:7070/healthz"
echo "  registry       localhost:5001"
echo "  kubeconfig     $KUBECONFIG"
```

- [ ] **Step 4: Write `down.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose down -v
rm -f .kubeconfig/kubeconfig.yaml
echo "kilvin infra down (volumes removed; allocator ledger and registry reset)"
```

- [ ] **Step 5: Validate syntax + commit**

```bash
chmod +x kilvin-py/infra/up.sh kilvin-py/infra/down.sh
docker compose -f kilvin-py/infra/docker-compose.yml config -q && echo compose-ok
bash -n kilvin-py/infra/up.sh && bash -n kilvin-py/infra/down.sh && echo scripts-ok
git add kilvin-py/infra
git commit -m "Add the compose control plane: temporal, allocator, registry, k3s"
```

---

### Task 4: `kilvin_py/config.py` + `kilvin_py/proc.py` (env settings, logged subprocesses)

**Files:**
- Create: `kilvin-py/kilvin_py/config.py`
- Create: `kilvin-py/kilvin_py/proc.py`
- Test: `tests/test_kilvin_helpers.py` (new file; more tests added in Tasks 5-6)

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kilvin-py"))

from kilvin_py.config import KilvinSettings  # noqa: E402
from kilvin_py.proc import SubprocessFailed, run_logged  # noqa: E402


def test_settings_defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = KilvinSettings.load()
    assert settings.temporal_address == "localhost:7233"
    assert settings.allocator_url == "http://localhost:7070"
    assert settings.registry == "localhost:5001"
    assert settings.namespace == "kilvin-training"
    assert settings.trainer_dir.name == "trainer"
    assert settings.kubeconfig_path.name == "kubeconfig.yaml"

    monkeypatch.setenv("KILVIN_ALLOCATOR_URL", "http://allocator:7070")
    assert KilvinSettings.load().allocator_url == "http://allocator:7070"


def test_run_logged_captures_output_and_raises_with_tail() -> None:
    lines = asyncio.run(run_logged([sys.executable, "-c", "print('a'); print('b')"], label="ok"))
    assert lines == ["a", "b"]

    with pytest.raises(SubprocessFailed) as err:
        asyncio.run(
            run_logged(
                [sys.executable, "-c", "print('boom-detail'); raise SystemExit(3)"],
                label="fails",
            )
        )
    assert "boom-detail" in str(err.value)
    assert "exit 3" in str(err.value)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/test_kilvin_helpers.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'kilvin_py.config'`

- [ ] **Step 3: Write `config.py`**

```python
"""Environment-driven settings for the host worker and starter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

KILVIN_PY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class KilvinSettings:
    temporal_address: str
    allocator_url: str
    registry: str
    namespace: str
    trainer_dir: Path
    kubeconfig_path: Path

    @classmethod
    def load(cls) -> "KilvinSettings":
        return cls(
            temporal_address=os.environ.get("KILVIN_TEMPORAL_ADDRESS", "localhost:7233"),
            allocator_url=os.environ.get("KILVIN_ALLOCATOR_URL", "http://localhost:7070"),
            registry=os.environ.get("KILVIN_REGISTRY", "localhost:5001"),
            namespace=os.environ.get("KILVIN_K8S_NAMESPACE", "kilvin-training"),
            trainer_dir=Path(os.environ.get("KILVIN_TRAINER_DIR", KILVIN_PY_ROOT / "trainer")),
            kubeconfig_path=Path(
                os.environ.get(
                    "KILVIN_KUBECONFIG", KILVIN_PY_ROOT / "infra" / ".kubeconfig" / "kubeconfig.yaml"
                )
            ),
        )
```

- [ ] **Step 4: Write `proc.py`**

```python
"""Async subprocess runner that captures output and heartbeats inside activities."""

from __future__ import annotations

import asyncio
from pathlib import Path

from temporalio import activity

TAIL_LINES = 40
HEARTBEAT_EVERY = 20


class SubprocessFailed(RuntimeError):
    """Command exited non-zero; message carries the output tail."""


def _maybe_heartbeat(label: str, line_count: int) -> None:
    try:
        if activity.in_activity():
            activity.heartbeat({"phase": label, "lines": line_count})
    except Exception:
        pass


async def run_logged(cmd: list[str], *, cwd: Path | None = None, label: str) -> list[str]:
    """Run a command, streaming combined output into a list of lines.

    Heartbeats every HEARTBEAT_EVERY lines when called from inside a Temporal
    activity so long docker builds keep the activity alive. Raises
    SubprocessFailed with the last TAIL_LINES lines on non-zero exit.
    """

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    lines: list[str] = []
    assert process.stdout is not None
    _maybe_heartbeat(label, 0)
    async for raw in process.stdout:
        lines.append(raw.decode(errors="replace").rstrip("\n"))
        if len(lines) % HEARTBEAT_EVERY == 0:
            _maybe_heartbeat(label, len(lines))
    code = await process.wait()
    _maybe_heartbeat(label, len(lines))
    if code != 0:
        tail = "\n".join(lines[-TAIL_LINES:])
        raise SubprocessFailed(f"{label}: {' '.join(cmd)} -> exit {code}\n{tail}")
    return lines
```

- [ ] **Step 5: Run tests, then commit**

Run: `uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/test_kilvin_helpers.py -q` — Expected: 2 passed

```bash
git add kilvin-py/kilvin_py/config.py kilvin-py/kilvin_py/proc.py tests/test_kilvin_helpers.py
git commit -m "Add env settings and a heartbeating logged-subprocess runner"
```

---

### Task 5: `kilvin_py/allocator_client.py`

**Files:**
- Create: `kilvin-py/kilvin_py/allocator_client.py`
- Modify: `tests/test_kilvin_helpers.py` (append)
- Modify: `kilvin-py/pyproject.toml` (add `httpx>=0.27`, `kubernetes>=29.0`)

- [ ] **Step 1: Append failing tests to `tests/test_kilvin_helpers.py`**

```python
import httpx  # add to imports at top of file

from kilvin_py.allocator_client import (  # noqa: E402
    AllocatorClient,
    AllocatorUnavailable,
    QuotaExhausted,
)


def _client_with(handler) -> AllocatorClient:
    return AllocatorClient("http://allocator.test", transport=httpx.MockTransport(handler))


def test_allocator_client_returns_grant() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/allocations"
        return httpx.Response(
            200,
            json={
                "allocation_id": "alloc-1",
                "cluster": "local-k3s",
                "cpus_granted": 2,
                "memory_gb_granted": 4,
                "quota_decision": {"cluster": "local-k3s", "reason": "fits"},
            },
        )

    grant = asyncio.run(
        _client_with(handler).request_allocation(run_id="r", stage_id="pretrain", cpus=2, memory_gb=4)
    )
    assert grant.allocation_id == "alloc-1"
    assert grant.quota_decision["reason"] == "fits"


def test_allocator_client_maps_409_and_connect_errors() -> None:
    def exhausted(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "quota exhausted on local-k3s"})

    with pytest.raises(QuotaExhausted, match="quota exhausted"):
        asyncio.run(
            _client_with(exhausted).request_allocation(run_id="r", stage_id="s", cpus=9, memory_gb=1)
        )

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(AllocatorUnavailable, match="run kilvin-py/infra/up.sh"):
        asyncio.run(
            _client_with(unreachable).request_allocation(run_id="r", stage_id="s", cpus=1, memory_gb=1)
        )


def test_allocator_client_release() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/v1/allocations/alloc-1"
        return httpx.Response(200, json={"released": "alloc-1"})

    asyncio.run(_client_with(handler).release("alloc-1"))
```

- [ ] **Step 2: Run to verify failure** (ModuleNotFoundError), then write `allocator_client.py`

```python
"""HTTP client for the resource-allocator service, with typed error mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

UP_HINT = "is the infra up? run kilvin-py/infra/up.sh"


class QuotaExhausted(Exception):
    """Pool has no capacity right now; retryable by Temporal policy."""


class AllocatorUnavailable(Exception):
    """The allocator service is unreachable; not retryable, infra is down."""


@dataclass(frozen=True)
class AllocationGrant:
    allocation_id: str
    cluster: str
    cpus_granted: int
    memory_gb_granted: int
    quota_decision: dict[str, Any]


class AllocatorClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, transport=self._transport, timeout=10.0)

    async def request_allocation(
        self, *, run_id: str, stage_id: str, cpus: int, memory_gb: int
    ) -> AllocationGrant:
        try:
            async with self._client() as client:
                response = await client.post(
                    "/v1/allocations",
                    json={"run_id": run_id, "stage_id": stage_id, "cpus": cpus, "memory_gb": memory_gb},
                )
        except httpx.HTTPError as err:
            raise AllocatorUnavailable(f"allocator at {self._base_url} unreachable ({err}); {UP_HINT}") from err
        if response.status_code == 409:
            raise QuotaExhausted(response.json().get("detail", "quota exhausted"))
        response.raise_for_status()
        body = response.json()
        return AllocationGrant(
            allocation_id=body["allocation_id"],
            cluster=body["cluster"],
            cpus_granted=body["cpus_granted"],
            memory_gb_granted=body["memory_gb_granted"],
            quota_decision=body["quota_decision"],
        )

    async def release(self, allocation_id: str) -> None:
        try:
            async with self._client() as client:
                response = await client.delete(f"/v1/allocations/{allocation_id}")
        except httpx.HTTPError as err:
            raise AllocatorUnavailable(f"allocator at {self._base_url} unreachable ({err}); {UP_HINT}") from err
        if response.status_code not in (200, 404):
            response.raise_for_status()
```

- [ ] **Step 3: Add deps to `kilvin-py/pyproject.toml`**

```toml
dependencies = [
    "temporalio>=1.11.0",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "kubernetes>=29.0",
]
```

- [ ] **Step 4: Run tests (5 passed in the file), commit**

```bash
git add kilvin-py/kilvin_py/allocator_client.py kilvin-py/pyproject.toml tests/test_kilvin_helpers.py
git commit -m "Add the allocator HTTP client with quota/unavailable error mapping"
```

---

### Task 6: `kilvin_py/k8s_manifest.py` + `kilvin_py/k8s_jobs.py`

**Files:**
- Create: `kilvin-py/kilvin_py/k8s_manifest.py`
- Create: `kilvin-py/kilvin_py/k8s_jobs.py` (lazy kubernetes imports — tests never need the package)
- Modify: `tests/test_kilvin_helpers.py` (append)

- [ ] **Step 1: Append failing manifest tests**

```python
from kilvin_py.k8s_manifest import render_job_manifest  # noqa: E402


def test_render_job_manifest_is_the_literal_launch_spec() -> None:
    manifest = render_job_manifest(
        job_name="kilvin-pretrain-abc123",
        namespace="kilvin-training",
        image="localhost:5001/kilvin-trainer@sha256:deadbeef",
        env={"MAX_STEPS": "200", "MODEL_NAME": "model-x"},
        cpus=2,
        memory_gb=4,
        run_id="run-a",
        stage_id="pretrain",
    )

    assert manifest["kind"] == "Job"
    assert manifest["metadata"]["namespace"] == "kilvin-training"
    assert manifest["metadata"]["labels"]["kilvin.run-id"] == "run-a"
    spec = manifest["spec"]
    assert spec["backoffLimit"] == 0  # Temporal owns retries, not the kubelet
    pod = spec["template"]["spec"]
    assert pod["restartPolicy"] == "Never"
    container = pod["containers"][0]
    assert container["image"].endswith("@sha256:deadbeef")
    assert {"name": "MAX_STEPS", "value": "200"} in container["env"]
    assert container["resources"]["requests"]["cpu"] == "2"
    assert container["resources"]["limits"]["memory"] == "4Gi"
```

- [ ] **Step 2: Verify failure, then write `k8s_manifest.py`**

```python
"""Render the Kubernetes Job manifest: the literal launch spec for one stage."""

from __future__ import annotations

from typing import Any


def render_job_manifest(
    *,
    job_name: str,
    namespace: str,
    image: str,
    env: dict[str, str],
    cpus: int,
    memory_gb: int,
    run_id: str,
    stage_id: str,
) -> dict[str, Any]:
    resources = {"cpu": str(cpus), "memory": f"{memory_gb}Gi"}
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": {"app": "kilvin-trainer", "kilvin.run-id": run_id, "kilvin.stage-id": stage_id},
        },
        "spec": {
            # Temporal's retry policy owns re-attempts; the kubelet must not race it.
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "metadata": {"labels": {"app": "kilvin-trainer", "kilvin.run-id": run_id}},
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "trainer",
                            "image": image,
                            "env": [{"name": key, "value": value} for key, value in sorted(env.items())],
                            "resources": {"requests": dict(resources), "limits": dict(resources)},
                        }
                    ],
                },
            },
        },
    }
```

- [ ] **Step 3: Write `k8s_jobs.py`** (thin, lazy-importing; exercised by the live gate, not unit tests)

```python
"""Thin wrapper over the kubernetes client for Job submit/status/logs.

Imports kubernetes lazily so test environments without the package can still
import kilvin_py.activities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class KubeconfigMissing(Exception):
    """Kubeconfig not found; infra is not up."""


class KubernetesJobs:
    def __init__(self, kubeconfig_path: Path) -> None:
        if not kubeconfig_path.exists():
            raise KubeconfigMissing(
                f"kubeconfig not found at {kubeconfig_path}; is the infra up? run kilvin-py/infra/up.sh"
            )
        self._kubeconfig = str(kubeconfig_path)

    def _clients(self):
        from kubernetes import client, config

        api_client = config.new_client_from_config(config_file=self._kubeconfig)
        return client.BatchV1Api(api_client), client.CoreV1Api(api_client)

    def create_job(self, manifest: dict[str, Any]) -> tuple[str, str]:
        batch, _ = self._clients()
        created = batch.create_namespaced_job(namespace=manifest["metadata"]["namespace"], body=manifest)
        return created.metadata.name, created.metadata.uid

    def job_status(self, name: str, namespace: str) -> str:
        """Return RUNNING, SUCCEEDED, or FAILED based on Job conditions."""
        batch, _ = self._clients()
        status = batch.read_namespaced_job_status(name=name, namespace=namespace).status
        for condition in status.conditions or []:
            if condition.type == "Complete" and condition.status == "True":
                return "SUCCEEDED"
            if condition.type == "Failed" and condition.status == "True":
                return "FAILED"
        return "RUNNING"

    def pod_log_tail(self, job_name: str, namespace: str, lines: int = 40) -> list[str]:
        _, core = self._clients()
        pods = core.list_namespaced_pod(namespace=namespace, label_selector="app=kilvin-trainer").items
        pods = [p for p in pods if (p.metadata.labels or {}).get("job-name") == job_name]
        if not pods:
            return []
        try:
            text = core.read_namespaced_pod_log(
                name=pods[-1].metadata.name, namespace=namespace, tail_lines=lines
            )
        except Exception as err:  # pod may not have logs yet
            return [f"<no logs: {err}>"]
        return text.splitlines()[-lines:]
```

- [ ] **Step 4: Run the helper test file (6 passed), commit**

```bash
git add kilvin-py/kilvin_py/k8s_manifest.py kilvin-py/kilvin_py/k8s_jobs.py tests/test_kilvin_helpers.py
git commit -m "Add the Job manifest renderer and lazy kubernetes wrapper"
```

---

### Task 7: Models rename + reshape (`ream` removal)

**Files:**
- Modify: `kilvin-py/kilvin_py/models.py`
- Modify: `kilvin-py/kilvin_py/workflows.py` (imports + skip_results + field uses; full step rewiring lands in Task 8)

Replace these dataclasses in `models.py` (leave everything else as-is):

- [ ] **Step 1: Reshape the intent/IO models**

```python
@dataclass(frozen=True)
class TrainingIntent:
    """The interpreted intent: what to train, with which image and resources."""

    model_output_tos_key: str
    workflow_config_uri: str
    checkpoint: str | None
    stage_index: int
    component_profile: dict[str, Any]
    image_ref: str = ""
    trainer_env: dict[str, str] | None = None
    cpus: int = 2
    memory_gb: int = 4


@dataclass(frozen=True)
class ConcretizeDependenciesInput:
    run_id: str
    checkpoint: str | None
    image_ref: str = ""


@dataclass(frozen=True)
class ConcretizeDependenciesOutput:
    image_ref: str
    image_digest: str
    lockfile_sha256: str


@dataclass(frozen=True)
class AllocateResourcesInput:
    """Reserve real CPU/memory capacity from the allocator for one stage."""

    run_id: str
    stage_id: str
    stage_index: int
    dataset_uri: str
    cpus: int = 2
    memory_gb: int = 4


@dataclass(frozen=True)
class QuotaDecision:
    """Why this placement was granted: capacity at decision time, on which cluster."""

    cluster: str
    cpus_requested: int
    cpus_granted: int
    memory_gb_requested: int
    memory_gb_granted: int
    cpus_available_before: int
    memory_gb_available_before: int
    reason: str


@dataclass(frozen=True)
class ResourceAllocationOutput:
    """The allocator's grant: a real reservation against the finite ledger."""

    allocation_id: str
    cluster: str
    cpus: int
    memory_gb: int
    dataset_mount: str | None = None
    quota_decision: QuotaDecision | None = None


@dataclass(frozen=True)
class MaterializeTrainingBundleInput:
    ir_name: str
    checkpoint: str
    config_snapshot: str
    allocation: ResourceAllocationOutput
    stage_index: int
    train_stage: str
    task_type: str
    image_ref: str
    trainer_env: dict[str, str]
    model: str
    run_id: str = ""
    namespace: str = "kilvin-training"


@dataclass(frozen=True)
class MaterializedBundleOutput:
    bundle_id: str
    bundle_path: str
    job_manifest: dict[str, Any]
    env_vars: dict[str, str]
    launch_plan: list[dict[str, Any]]
    health_checks: list[str]


@dataclass(frozen=True)
class SubmitK8sOutput:
    job_name: str
    job_uid: str
    k8s_namespace: str


@dataclass(frozen=True)
class MonitorTrainingInput:
    job_name: str
    job_uid: str
    ir_name: str
    k8s_namespace: str
    allocation_id: str = ""
```

(`SubmitK8sInput`, `MonitorOutput`, `ArtifactWriteInput`, signals, envelopes stay unchanged. The old `ReamAllocationOutput`, `rendezvous`, `token_plan`, `runtime_setup`, `bound_components`, `primus_*` fields are deleted.)

- [ ] **Step 2: Case-sensitive sweep proves the term is gone from our code**

Run: `grep -rn "Ream\|ream" kilvin-py/ explorer/scripts explorer/src HACKERS_GUIDE.md --include="*.py" --include="*.tsx" --include="*.md" | grep -v ".venv" | grep -iv "stream"`
Expected after Tasks 7-10: no matches in kilvin-py (generator string is fixed in Task 10).

- [ ] **Step 3: Commit together with Task 8** (workflows.py won't import until Task 8 rewires it — do Tasks 7+8 as one commit).

---

### Task 8: Workflow rewiring + worker/starter env config

**Files:**
- Modify: `kilvin-py/kilvin_py/workflows.py`
- Modify: `kilvin-py/worker.py`
- Modify: `kilvin-py/start_workflow.py`

- [ ] **Step 1: Update `workflows.py` imports and the `run()` step calls** (the `_run_step` envelope, signals, queries are untouched; every `step_name="…"` line stays byte-identical)

Imports: replace `ReamAllocationOutput` with `ResourceAllocationOutput`; drop unused models.

`interpret_intent` call: unchanged input; new `skip_result` (laptop-scale fields with deterministic values):

```python
            skip_result=TrainingIntent(
                model_output_tos_key=input.job_params_uri,
                workflow_config_uri=f"file://./.kilvin-cache/{input.run_config.run_id}/workflow.yaml",
                checkpoint="s3://checkpoints/model-x/base",
                stage_index=0,
                component_profile={
                    "run_name": input.run_config.kilvin_run_name,
                    "model": "model-x",
                    "dataset_root": stages[0].dataset_profile.uri,
                    "spec_version": input.run_config.workflow_spec,
                },
                image_ref=f"localhost:5001/kilvin-trainer:{input.run_config.run_id}",
                trainer_env={},
            ),
```

`concretize_dependencies` call:

```python
        concretized = await self._run_step(
            input=input,
            stage=stages[0],
            stage_index=0,
            step_name="concretize_dependencies",
            activity_fn=activities.concretize_dependencies,
            activity_input=ConcretizeDependenciesInput(
                run_id=input.run_config.run_id,
                checkpoint=intent.checkpoint,
                image_ref=intent.image_ref,
            ),
            timeout_seconds=900,
            skip_result=ConcretizeDependenciesOutput(
                image_ref=intent.image_ref,
                image_digest="sha256:replayed",
                lockfile_sha256="replayed",
            ),
        )

        checkpoint = intent.checkpoint or "scratch"
        digest_ref = (
            f"{concretized.image_ref}@{concretized.image_digest}"
            if concretized.image_digest.startswith("sha256:")
            else concretized.image_ref
        )
        ir_name = f"kilvin-ir-{input.run_config.run_id}"
```

`allocate_resources` call (per stage):

```python
            allocation = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="allocate_resources",
                activity_fn=activities.allocate_resources,
                activity_input=AllocateResourcesInput(
                    run_id=input.run_config.run_id,
                    stage_id=stage.stage_id,
                    stage_index=stage_index,
                    dataset_uri=stage.dataset_profile.uri,
                    cpus=intent.cpus,
                    memory_gb=intent.memory_gb,
                ),
                timeout_seconds=180,
                retry_attempts=6,
                skip_result=ResourceAllocationOutput(
                    allocation_id=f"skip-allocation-{stage.stage_id}",
                    cluster="local-k3s",
                    cpus=1,
                    memory_gb=1,
                ),
            )
```

`materialize_training_bundle` call:

```python
            bundle = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="materialize_training_bundle",
                activity_fn=activities.materialize_training_bundle,
                activity_input=MaterializeTrainingBundleInput(
                    ir_name=f"{ir_name}-{stage.stage_id}",
                    checkpoint=checkpoint,
                    config_snapshot=intent.workflow_config_uri,
                    allocation=allocation,
                    stage_index=stage_index,
                    train_stage=stage.stage_id,
                    task_type="train",
                    image_ref=digest_ref,
                    trainer_env=dict(intent.trainer_env or {}),
                    model=intent.component_profile.get("model", "model-x"),
                    run_id=input.run_config.run_id,
                ),
                timeout_seconds=60,
                skip_result=MaterializedBundleOutput(
                    bundle_id=f"skip-bundle-{stage.stage_id}",
                    bundle_path="skipped://bundle",
                    job_manifest={},
                    env_vars={},
                    launch_plan=[],
                    health_checks=[],
                ),
            )
```

`submit_k8s_job` / `monitor_training` calls:

```python
            submit_out = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="submit_k8s_job",
                activity_fn=activities.submit_k8s_job,
                activity_input=SubmitK8sInput(
                    stage_id=stage.stage_id,
                    bundle=bundle,
                    namespace="kilvin-training",
                ),
                timeout_seconds=120,
                skip_result=SubmitK8sOutput(
                    job_name=f"replay-skip-{stage.stage_id}",
                    job_uid="skip-replay",
                    k8s_namespace="kilvin-training",
                ),
            )

            monitor_out = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="monitor_training",
                activity_fn=activities.monitor_training,
                activity_input=MonitorTrainingInput(
                    job_name=submit_out.job_name,
                    job_uid=submit_out.job_uid,
                    ir_name=f"{ir_name}-{stage.stage_id}",
                    k8s_namespace=submit_out.k8s_namespace,
                    allocation_id=allocation.allocation_id,
                ),
                timeout_seconds=3600,
                skip_result=MonitorOutput(final_status="SUCCEEDED"),
            )
```

The failure check, logs persistence, `checkpoint = f"{checkpoint}/{stage.stage_id}"`, replay clearing, and completion return stay exactly as they are.

- [ ] **Step 2: `worker.py`** — env-driven address, anchor intact:

```python
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from kilvin_py import activities, workflows
from kilvin_py.config import KilvinSettings
from start_workflow import TASK_QUEUE


async def main() -> None:
    settings = KilvinSettings.load()
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[workflows.KilvinTrainingWorkflow],
        activities=[
            activities.interpret_training_intent,
            activities.concretize_dependencies,
            activities.allocate_resources,
            activities.materialize_training_bundle,
            activities.submit_k8s_job,
            activities.monitor_training,
            activities.persist_yaml_artifact,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: `start_workflow.py`** — keep the production-shaped intent and the `result = await client.execute_workflow(` anchor; change only: `Client.connect(KilvinSettings.load().temporal_address)` (add the import), and extend the `sample_run_config` docstring with the two-scale line:

```python
    """One clean request: train model X on FineWeb with 64 A100 GPUs.

    The single pretrain stage keeps the whole walkthrough inspectable: one
    allocation, one materialized bundle, one Kubernetes job, and the hood-open
    artifacts the explorer points at (quota decision, env vars, job id, logs).

    Locally the same workflow materializes this intent for real at laptop
    scale: interpret_intent derives a tiny CPU GPT-2 trainer config, the
    allocator grants CPUs from a finite local ledger, and the job runs on the
    k3s cluster from kilvin-py/infra/docker-compose.yml.
    """
```

- [ ] **Step 4: Sanity-import + commit (Tasks 7+8 together)**

```bash
cd kilvin-py && uv run --with temporalio --with httpx python -c "from kilvin_py import workflows, models; print('imports ok')"
git add kilvin-py/kilvin_py/models.py kilvin-py/kilvin_py/workflows.py kilvin-py/worker.py kilvin-py/start_workflow.py
git commit -m "Rename ReamAllocationOutput to ResourceAllocationOutput and rewire the workflow for real activities"
```

(Note: `kilvin_py.activities` still references old model names until Task 9 — workflows.py imports activities, so run the import check from Task 9 if this one fails on activities; in that case fold Tasks 7-9 into one commit.)

---

### Task 9: Real activities

**Files:**
- Rewrite: `kilvin-py/kilvin_py/activities.py`

- [ ] **Step 1: Full new `activities.py`** (anchors `^async def allocate_resources\(` and `^async def monitor_training\(` preserved)

```python
from __future__ import annotations

import asyncio
import hashlib
import uuid

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .allocator_client import AllocatorClient, AllocatorUnavailable, QuotaExhausted
from .artifacts import ArtifactStore
from .config import KilvinSettings
from .k8s_jobs import KubeconfigMissing, KubernetesJobs
from .k8s_manifest import render_job_manifest
from .models import (
    AllocateResourcesInput,
    ArtifactWriteInput,
    ConcretizeDependenciesInput,
    ConcretizeDependenciesOutput,
    InterpretIntentInput,
    MaterializedBundleOutput,
    MaterializeTrainingBundleInput,
    MonitorOutput,
    MonitorTrainingInput,
    QuotaDecision,
    ResourceAllocationOutput,
    SubmitK8sInput,
    SubmitK8sOutput,
    StepIOArtifact,
    TrainingIntent,
)
from .proc import SubprocessFailed, run_logged

# Two-scale mapping: the intent is production-shaped (FineWeb, 64 A100s); the
# local materialization trains a tiny CPU GPT-2 with the same workflow.
LAPTOP_TRAINER_DEFAULTS = {
    "N_LAYER": "4",
    "N_HEAD": "4",
    "N_EMBD": "128",
    "BLOCK_SIZE": "128",
    "BATCH_SIZE": "8",
    "LEARNING_RATE": "0.0003",
    "SEED": "1337",
    "LOG_EVERY": "10",
    "DATA_PATH": "/app/data/input.txt",
    "OUT_DIR": "/output",
}
LAPTOP_MAX_STEPS = 200
MONITOR_POLL_SECONDS = 5


@activity.defn
async def interpret_training_intent(input: InterpretIntentInput) -> TrainingIntent:
    """Turn the researcher's intent into the typed plan the workflow executes."""

    settings = KilvinSettings.load()
    run_config = input.run_config
    run_stages = run_config.stages
    stage = run_stages[0]
    stage_zero_dataset = stage.dataset_profile.uri if run_stages else "hdfs://datasets/fineweb"

    trainer_env = dict(LAPTOP_TRAINER_DEFAULTS)
    trainer_env.update(
        {
            "RUN_ID": run_config.run_id,
            "MODEL_NAME": "model-x",
            "TRAIN_STAGE": stage.stage_id,
            "MAX_STEPS": str(min(stage.runtime_profile.max_steps, LAPTOP_MAX_STEPS)),
        }
    )

    return TrainingIntent(
        model_output_tos_key=input.job_params_uri,
        workflow_config_uri=f"file://./.kilvin-cache/{run_config.run_id}/workflow.yaml",
        checkpoint="s3://checkpoints/model-x/base",
        stage_index=0,
        component_profile={
            "run_name": run_config.kilvin_run_name,
            "model": "model-x",
            "dataset_root": stage_zero_dataset,
            "spec_version": run_config.workflow_spec,
        },
        image_ref=f"{settings.registry}/kilvin-trainer:{run_config.run_id}",
        trainer_env=trainer_env,
        cpus=2,
        memory_gb=4,
    )


@activity.defn
async def concretize_dependencies(
    input: ConcretizeDependenciesInput,
) -> ConcretizeDependenciesOutput:
    """Build the training image and pin dependencies into a concrete code bundle."""

    settings = KilvinSettings.load()
    trainer_dir = settings.trainer_dir
    lockfile = trainer_dir / "uv.lock"
    if not lockfile.exists():
        raise ApplicationError(
            f"trainer lockfile missing at {lockfile}; run `uv lock` in {trainer_dir}",
            non_retryable=True,
        )

    try:
        await run_logged(["uv", "lock", "--check"], cwd=trainer_dir, label="uv-lock-check")
        await run_logged(
            ["docker", "build", "-t", input.image_ref, "."], cwd=trainer_dir, label="docker-build"
        )
        await run_logged(["docker", "push", input.image_ref], cwd=trainer_dir, label="docker-push")
        inspect = await run_logged(
            ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", input.image_ref],
            label="docker-inspect",
        )
    except SubprocessFailed as err:
        raise ApplicationError(str(err), type="BuildFailed") from err

    repo_digest = inspect[-1].strip()  # e.g. localhost:5001/kilvin-trainer@sha256:abc...
    if "@sha256:" not in repo_digest:
        raise ApplicationError(f"could not resolve image digest from {repo_digest!r}", type="BuildFailed")
    digest = repo_digest.split("@", 1)[1]

    return ConcretizeDependenciesOutput(
        image_ref=input.image_ref,
        image_digest=digest,
        lockfile_sha256=hashlib.sha256(lockfile.read_bytes()).hexdigest(),
    )


@activity.defn
async def allocate_resources(input: AllocateResourcesInput) -> ResourceAllocationOutput:
    """Gather quota/placement constraints, solve placement, and reserve resources."""

    settings = KilvinSettings.load()
    client = AllocatorClient(settings.allocator_url)
    try:
        grant = await client.request_allocation(
            run_id=input.run_id,
            stage_id=input.stage_id,
            cpus=input.cpus,
            memory_gb=input.memory_gb,
        )
    except QuotaExhausted as err:
        raise ApplicationError(str(err), type="QuotaExhausted") from err
    except AllocatorUnavailable as err:
        raise ApplicationError(str(err), non_retryable=True) from err

    return ResourceAllocationOutput(
        allocation_id=grant.allocation_id,
        cluster=grant.cluster,
        cpus=grant.cpus_granted,
        memory_gb=grant.memory_gb_granted,
        dataset_mount=input.dataset_uri,
        quota_decision=QuotaDecision(**grant.quota_decision),
    )


@activity.defn
async def materialize_training_bundle(
    input: MaterializeTrainingBundleInput,
) -> MaterializedBundleOutput:
    """Expand training intent into the concrete launch spec for this stage."""

    job_name = f"kilvin-{input.train_stage}-{uuid.uuid4().hex[:6]}"
    env_vars = dict(input.trainer_env)
    env_vars.setdefault("CHECKPOINT_URI", input.checkpoint)
    env_vars.setdefault("DATASET_MOUNT", input.allocation.dataset_mount or "")

    manifest = render_job_manifest(
        job_name=job_name,
        namespace=input.namespace,
        image=input.image_ref,
        env=env_vars,
        cpus=input.allocation.cpus,
        memory_gb=input.allocation.memory_gb,
        run_id=input.run_id,
        stage_id=input.train_stage,
    )

    return MaterializedBundleOutput(
        bundle_id=f"bundle-{uuid.uuid4().hex[:10]}",
        bundle_path=f"{input.config_snapshot}/bundle/{input.train_stage}.yaml",
        job_manifest=manifest,
        env_vars=env_vars,
        launch_plan=[{"entrypoint": "python trainer.py", "image": input.image_ref}],
        health_checks=["job-conditions", "pod-logs"],
    )


@activity.defn
async def submit_k8s_job(input: SubmitK8sInput) -> SubmitK8sOutput:
    """Create the rendered Job on the k3s cluster."""

    settings = KilvinSettings.load()
    try:
        jobs = KubernetesJobs(settings.kubeconfig_path)
        name, uid = await asyncio.to_thread(jobs.create_job, input.bundle.job_manifest)
    except KubeconfigMissing as err:
        raise ApplicationError(str(err), non_retryable=True) from err
    return SubmitK8sOutput(job_name=name, job_uid=uid, k8s_namespace=input.namespace)


@activity.defn
async def monitor_training(input: MonitorTrainingInput) -> MonitorOutput:
    """Watch the Job until completion, heartbeating; release the allocation."""

    settings = KilvinSettings.load()
    try:
        jobs = KubernetesJobs(settings.kubeconfig_path)
    except KubeconfigMissing as err:
        raise ApplicationError(str(err), non_retryable=True) from err

    status = "RUNNING"
    while status == "RUNNING":
        status = await asyncio.to_thread(jobs.job_status, input.job_name, input.k8s_namespace)
        activity.heartbeat(
            {"job_name": input.job_name, "namespace": input.k8s_namespace, "status": status}
        )
        if status == "RUNNING":
            await asyncio.sleep(MONITOR_POLL_SECONDS)

    log_tail = await asyncio.to_thread(jobs.pod_log_tail, input.job_name, input.k8s_namespace, 40)

    if input.allocation_id and not input.allocation_id.startswith("skip-"):
        try:
            await AllocatorClient(settings.allocator_url).release(input.allocation_id)
        except AllocatorUnavailable:
            pass  # the run outcome stands; leaked allocations are visible via GET /v1/allocations

    logs_uri = f"k8s://{input.k8s_namespace}/jobs/{input.job_name}/logs"
    return MonitorOutput(
        final_status="SUCCESS" if status == "SUCCEEDED" else "FAILED",
        running_pods=0,
        total_pods=1,
        logs_uri=logs_uri,
        log_tail=log_tail,
    )


@activity.defn
async def persist_yaml_artifact(input: ArtifactWriteInput) -> StepIOArtifact:
    """Persist an input or output payload for deterministic inspectability."""

    store = ArtifactStore(root_uri="file://./.kilvin-artifacts")
    artifact = store.write_yaml(
        input.run_id,
        input.run_attempt,
        input.artifact_name,
        input.payload,
    )
    return artifact
```

- [ ] **Step 2: Import check + commit**

```bash
cd kilvin-py && uv run --with temporalio --with httpx python -c "from kilvin_py import activities; print('activities ok')"
git add kilvin-py/kilvin_py/activities.py
git commit -m "Make the six activities real: uv+docker build, allocator HTTP, k3s jobs"
```

---

### Task 10: Rewrite the story tests + workflow-orchestration test with fakes

**Files:**
- Rewrite: `tests/test_kilvin_training_story.py`

- [ ] **Step 1: New test file** (intent derivation is pure; orchestration runs in the time-skipping env with fakes registered under the real activity names; the time-skipping env downloads a test server binary on first run — that's expected)

```python
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import pytest
from temporalio import activity
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

ROOT = Path(__file__).resolve().parents[1]
KILVIN_PY = ROOT / "kilvin-py"
sys.path.insert(0, str(KILVIN_PY))

import start_workflow  # noqa: E402
from kilvin_py import activities, models  # noqa: E402
from kilvin_py.k8s_manifest import render_job_manifest  # noqa: E402
from kilvin_py.workflows import KilvinTrainingWorkflow  # noqa: E402


def test_sample_run_config_is_the_single_training_intent() -> None:
    config = start_workflow.sample_run_config()

    assert config.kilvin_run_name == "model-x-fineweb-64xa100"
    assert config.stage_sequence == ["pretrain"]
    assert len(config.stages) == 1
    assert config.stages[0].dataset_profile.uri == start_workflow.INTENT_DATASET_URI
    assert start_workflow.workflow_id_for_run("run-demo") == "kilvin-training-run-demo"
    assert start_workflow.TASK_QUEUE == "kilvin-training-task-queue"
    assert "laptop" in (start_workflow.sample_run_config.__doc__ or "").lower()


def test_interpret_intent_derives_the_laptop_scale_plan() -> None:
    config = start_workflow.sample_run_config()
    intent = asyncio.run(
        activities.interpret_training_intent(
            models.InterpretIntentInput(
                run_config=config,
                job_params_uri=f"hdfs://params/{config.run_id}/params.yaml",
            )
        )
    )

    assert intent.component_profile["model"] == "model-x"
    assert intent.image_ref == f"localhost:5001/kilvin-trainer:{config.run_id}"
    env = intent.trainer_env or {}
    assert env["MAX_STEPS"] == "200"  # production max_steps capped to laptop scale
    assert env["TRAIN_STAGE"] == "pretrain"
    assert env["RUN_ID"] == config.run_id
    assert int(env["N_LAYER"]) >= 1
    assert intent.cpus == 2 and intent.memory_gb == 4


def test_materialize_renders_the_literal_job_manifest() -> None:
    allocation = models.ResourceAllocationOutput(
        allocation_id="alloc-1", cluster="local-k3s", cpus=2, memory_gb=4, dataset_mount="hdfs://d"
    )
    bundle = asyncio.run(
        activities.materialize_training_bundle(
            models.MaterializeTrainingBundleInput(
                ir_name="kilvin-ir-run-a-pretrain",
                checkpoint="s3://checkpoints/model-x/base",
                config_snapshot="file://./.kilvin-cache/run-a/workflow.yaml",
                allocation=allocation,
                stage_index=0,
                train_stage="pretrain",
                task_type="train",
                image_ref="localhost:5001/kilvin-trainer@sha256:abc",
                trainer_env={"MAX_STEPS": "200", "RUN_ID": "run-a"},
                model="model-x",
                run_id="run-a",
            )
        )
    )

    manifest = bundle.job_manifest
    assert manifest["spec"]["backoffLimit"] == 0
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "localhost:5001/kilvin-trainer@sha256:abc"
    assert {"name": "MAX_STEPS", "value": "200"} in container["env"]
    assert bundle.env_vars["CHECKPOINT_URI"] == "s3://checkpoints/model-x/base"


def test_workflow_persists_explorer_artifact_names() -> None:
    workflow_source = (KILVIN_PY / "kilvin_py" / "workflows.py").read_text(encoding="utf-8")
    readme = (KILVIN_PY / "README.md").read_text(encoding="utf-8")

    for artifact in ["quota_decision", "env_vars", "logs"]:
        assert f'artifact_label="{artifact}"' in workflow_source
        assert f"{artifact}.yaml" in readme

    assert "kilvin-training-run-<id>" in readme
    assert "CMD" not in readme
    assert "outer loop" not in readme.lower()


def _fake_activities() -> list:
    @activity.defn(name="interpret_training_intent")
    async def fake_interpret(input: models.InterpretIntentInput) -> models.TrainingIntent:
        return models.TrainingIntent(
            model_output_tos_key=input.job_params_uri,
            workflow_config_uri="file://./.kilvin-cache/test/workflow.yaml",
            checkpoint="s3://checkpoints/model-x/base",
            stage_index=0,
            component_profile={"model": "model-x", "run_name": "t", "dataset_root": "d", "spec_version": "v"},
            image_ref="localhost:5001/kilvin-trainer:test",
            trainer_env={"MAX_STEPS": "1"},
        )

    @activity.defn(name="concretize_dependencies")
    async def fake_concretize(
        input: models.ConcretizeDependenciesInput,
    ) -> models.ConcretizeDependenciesOutput:
        return models.ConcretizeDependenciesOutput(
            image_ref=input.image_ref, image_digest="sha256:fake", lockfile_sha256="fake"
        )

    @activity.defn(name="allocate_resources")
    async def fake_allocate(input: models.AllocateResourcesInput) -> models.ResourceAllocationOutput:
        return models.ResourceAllocationOutput(
            allocation_id="alloc-fake", cluster="local-k3s", cpus=input.cpus, memory_gb=input.memory_gb
        )

    @activity.defn(name="materialize_training_bundle")
    async def fake_materialize(
        input: models.MaterializeTrainingBundleInput,
    ) -> models.MaterializedBundleOutput:
        manifest = render_job_manifest(
            job_name="kilvin-test",
            namespace=input.namespace,
            image=input.image_ref,
            env=input.trainer_env,
            cpus=input.allocation.cpus,
            memory_gb=input.allocation.memory_gb,
            run_id=input.run_id,
            stage_id=input.train_stage,
        )
        return models.MaterializedBundleOutput(
            bundle_id="bundle-fake",
            bundle_path="fake://bundle",
            job_manifest=manifest,
            env_vars=dict(input.trainer_env),
            launch_plan=[],
            health_checks=[],
        )

    @activity.defn(name="submit_k8s_job")
    async def fake_submit(input: models.SubmitK8sInput) -> models.SubmitK8sOutput:
        return models.SubmitK8sOutput(job_name="kilvin-test", job_uid="uid-1", k8s_namespace=input.namespace)

    @activity.defn(name="monitor_training")
    async def fake_monitor(input: models.MonitorTrainingInput) -> models.MonitorOutput:
        return models.MonitorOutput(final_status="SUCCESS", log_tail=["step=1 loss=4.2"])

    return [
        fake_interpret,
        fake_concretize,
        fake_allocate,
        fake_materialize,
        fake_submit,
        fake_monitor,
        activities.persist_yaml_artifact,
    ]


@pytest.mark.asyncio
async def test_workflow_orchestrates_six_steps_and_pause_resume_with_fakes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # .kilvin-artifacts lands in tmp
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        client: Client = env.client
        task_queue = f"kilvin-test-{uuid.uuid4().hex[:6]}"
        config = start_workflow.sample_run_config()

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[KilvinTrainingWorkflow],
            activities=_fake_activities(),
        ):
            handle = await client.start_workflow(
                KilvinTrainingWorkflow.run,
                models.TrainingWorkflowInput(run_id=config.run_id, run_config=config),
                id=f"kilvin-test-{config.run_id}",
                task_queue=task_queue,
            )
            await handle.signal(KilvinTrainingWorkflow.pause)
            status = await handle.query(KilvinTrainingWorkflow.run_status)
            assert status.paused is True
            await handle.signal(KilvinTrainingWorkflow.resume)

            result = await handle.result()
            assert result == f"KILVIN_TRAINING_COMPLETED:{config.run_id}"

            trace = await handle.query(KilvinTrainingWorkflow.run_step_trace)
            succeeded = [t.step_name for t in trace if t.status == "SUCCEEDED"]
            assert succeeded == [
                "interpret_intent",
                "concretize_dependencies",
                "allocate_resources",
                "materialize_training_bundle",
                "submit_k8s_job",
                "monitor_training",
            ]
    finally:
        await env.shutdown()
```

- [ ] **Step 2: Run the full suite**

Run: `uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/ -q`
Expected: all pass (the old `test_activities_materialize_the_same_hood_open_story` and `test_workflow_skip_paths_preserve_the_same_training_intent` are replaced by the new tests above; generator tests still pass because anchors are intact). If `pytest.mark.asyncio` is unsupported by config, wrap the body in `asyncio.run()` inside a sync test instead.

- [ ] **Step 3: Commit**

```bash
git add tests/test_kilvin_training_story.py
git commit -m "Test orchestration with fake activities and the real pure helpers"
```

---

### Task 11: Story surfaces (generator, guide, Basics, READMEs) + regen

**Files:**
- Modify: `explorer/scripts/build_lifecycle_data.py` (the `kilvin_internals` authored content + the two node notes that mention simulation)
- Modify: `HACKERS_GUIDE.md` (§3 and §6 copy; anchors untouched)
- Modify: `explorer/src/basics/BasicsExplorer.tsx` + `BasicsExplorer.test.tsx` (two-scale line)
- Rewrite: `kilvin-py/README.md`
- Modify: `README.md`, `AGENTS.md` (one-liners)
- Regenerate: `explorer/public/data/**`, `explorer/public/HACKERS_GUIDE.md`

- [ ] **Step 1: Generator `kilvin_internals` content updates** — in `build_lifecycle_data.py`:
  - `output_model="ReamAllocationOutput"` → `"ResourceAllocationOutput"`.
  - `concretize_dependencies` step summary/details → "Runs `uv lock --check`, builds the trainer image with `docker build` (the Dockerfile runs `uv sync --frozen`), pushes it to the local registry, and returns the digest-pinned reference plus the lockfile SHA."
  - `allocate_resources` step details → "POSTs to the resource-allocator service, which holds a finite CPU/memory ledger for the local-k3s cluster; a 409 (pool exhausted) becomes a retryable error so Temporal's retry policy is the real backoff loop. The real quota decision is persisted as quota_decision.yaml."
  - `materialize_training_bundle` details → mention the rendered Job manifest is the literal launch spec (digest-pinned image, env vars, backoffLimit 0).
  - `submit_k8s_job` summary → "Creates the Job on the k3s cluster (from kilvin-py/infra/docker-compose.yml) in the kilvin-training namespace." Remove "Primus" wording.
  - `monitor_training` details → polls Job conditions and pod logs with heartbeats, persists logs.yaml before the failure check, releases the allocation.
  - Workflow card details: append "Locally everything is real at laptop scale: a tiny CPU GPT-2 trainer image, CPU quota from a local allocator, a k3s cluster in docker compose."
  - timeout in the `concretize_dependencies` step entry: 900.

- [ ] **Step 2: HACKERS_GUIDE.md** — §3: replace the parenthetical about the steps with real semantics ("concretizes dependencies (runs uv lock, builds and pushes the trainer image, pins the digest), allocates resources (reserves CPU quota from a local allocator service with a finite ledger), … submits the Kubernetes job to the k3s cluster from the compose stack, and monitors it through a heartbeating activity") and add the two-scale sentence: "The intent is production-shaped; locally the same workflow materializes it for real at laptop scale — a tiny CPU GPT-2 on tiny-shakespeare." §6 source map already points at `allocate_resources`/`monitor_training` — keep; update the §6 sentence "such as resource allocation or training monitoring" to mention they are real (allocator HTTP, k8s polling).

- [ ] **Step 3: BasicsExplorer** — in the hero/intro copy add one sentence (and assert it in the test): `In this repo the same workflow materializes that intent for real at laptop scale: a tiny CPU GPT-2, quota from a local allocator, and a Kubernetes job on k3s — all from one docker compose stack.` Add to `BasicsExplorer.test.tsx`: `expect(screen.getByText(/for real at laptop scale/)).toBeTruthy()`.

- [ ] **Step 4: `kilvin-py/README.md`** — keep the story/table sections; replace the run instructions with:

```markdown
## Run it for real

Prereqs: docker (colima), kubectl, uv, python 3.10+.

1. `infra/up.sh` — brings up Temporal (+ UI at http://localhost:8080), the
   resource allocator, a local registry, and a k3s cluster, all via docker
   compose. First run downloads images; give colima ≥4 CPUs / 8GB
   (`colima start --cpu 4 --memory 8`).
2. `python worker.py` — host worker; it drives `uv`, `docker build/push`, and
   the k3s kubeconfig exported to `infra/.kubeconfig/kubeconfig.yaml`.
3. `python start_workflow.py` — one training run, end to end. First run builds
   the trainer image (torch CPU wheels; a few minutes — cached afterwards).
4. Watch: Temporal UI, `kubectl --kubeconfig infra/.kubeconfig/kubeconfig.yaml
   -n kilvin-training get jobs,pods`, `curl localhost:7070/v1/allocations`,
   and `.kilvin-artifacts/<run-id>/…` (quota_decision.yaml, env_vars.yaml,
   logs.yaml with the real loss curve).
5. `infra/down.sh` — tear down (resets the ledger and registry).
```
Keep the existing artifact-tree section and the workflow-id pattern `kilvin-training-run-<id>` (tests assert `quota_decision.yaml`/`env_vars.yaml`/`logs.yaml` and that pattern appear).

- [ ] **Step 5: README.md / AGENTS.md** — update the kilvin-py bullets to mention "real local materialization: uv+docker concretization, allocator ledger, k3s job via docker compose".

- [ ] **Step 6: Regenerate + run gates + commit**

```bash
uv run python explorer/scripts/build_lifecycle_data.py --repo-root .
uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/ -q
cd explorer && npm test && npm run build && cd ..
git add explorer/scripts/build_lifecycle_data.py explorer/public HACKERS_GUIDE.md \
        explorer/src/basics kilvin-py/README.md README.md AGENTS.md
git commit -m "Tell the real laptop-scale story across guide, internals, Basics, and READMEs"
```

---

### Task 12: Live validation (Tier 2 — the point)

No file changes; this is the gate. Capture outputs for the final report.

- [ ] **Step 1: Bring up infra**

```bash
kilvin-py/infra/up.sh
docker compose -f kilvin-py/infra/docker-compose.yml ps   # all services Up
curl -s localhost:7070/healthz                            # {"status":"ok",...}
```

- [ ] **Step 2: Sync worker venv and start the worker (background)**

```bash
cd kilvin-py && uv sync && nohup uv run python worker.py > /tmp/kilvin-worker.log 2>&1 &
```

- [ ] **Step 3: Run the workflow; assert the full chain**

```bash
cd kilvin-py && uv run python start_workflow.py    # expect Result: KILVIN_TRAINING_COMPLETED:run-…
export KUBECONFIG=$PWD/infra/.kubeconfig/kubeconfig.yaml
kubectl -n kilvin-training get jobs                # COMPLETIONS 1/1
temporal workflow query -w kilvin-training-<run_id> --type run_step_trace --address localhost:7233
grep -r "sha256:" .kilvin-artifacts/<run_id>/1/artifacts/pretrain/concretize_dependencies/out.yaml
cat .kilvin-artifacts/<run_id>/1/artifacts/pretrain/allocate_resources/quota_decision.yaml
grep "loss=" .kilvin-artifacts/<run_id>/1/artifacts/pretrain/monitor_training/logs.yaml | head
curl -s localhost:7070/v1/allocations              # [] — grant was released
```

Assert: six steps SUCCEEDED; real digest; real quota decision; decreasing loss lines; ledger empty.

- [ ] **Step 4: Control-path proof** — adapt `/tmp/control_path_check.py` from the previous round: start a second run with NO worker polling, signal `pause`, start the worker, observe PAUSED via `run_status`, `resume`, await completion.

- [ ] **Step 5: Quota-contention proof (cheap)** — `curl -X POST localhost:7070/v1/allocations -H 'content-type: application/json' -d '{"run_id":"hog","stage_id":"x","cpus":8,"memory_gb":16}'` to drain the pool, start a run, observe `allocate_resources` retrying (activity attempt > 1 in Temporal UI or `temporal workflow describe`), then `curl -X DELETE .../v1/allocations/<id>` and watch the run proceed to completion.

- [ ] **Step 6: Leave infra up for the aesthetic pass; record all evidence in the final report.**

---

### Task 13: Aesthetic pass + ship

- [ ] **Step 1: Screenshots** — `cd explorer && npm run preview -- --port 4173 --strictPort &`; agent-browser: Basics and Deep Dive→Kilvin Internals at 1440×900 and 390×844; check the new two-scale copy fits, internals step descriptions don't overflow the detail panel, reduced-motion still zeroes animations (`set media reduced-motion`), `document.documentElement.scrollWidth === 390` at mobile.

- [ ] **Step 2: Terminology consistency sweep**

```bash
grep -rn "uv sync\|uv lock\|digest\|k3s\|allocator" explorer/src/basics explorer/public/data/kilvin/internals.json HACKERS_GUIDE.md | head -30
grep -rni "primus\|ream" kilvin-py explorer/src explorer/scripts HACKERS_GUIDE.md --include='*.py' --include='*.tsx' --include='*.md' | grep -v .venv | grep -iv "stream"   # expect empty
```

- [ ] **Step 3: Final gates + push**

```bash
uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/ -q
cd explorer && npm test && npm run build && cd ..
git status --short   # only our files; monoctl test files stay untracked/unstaged
GIT_SSH_COMMAND="ssh -i ~/.ssh/phi9t_github -o IdentitiesOnly=yes" git push origin phi9t-mainline
```

- [ ] **Step 4: Verify Pages deploy by served content** (poll the live CSS/JS + `data/kilvin/internals.json` for the new step copy, e.g. `uv lock --check`), then tear down local infra if the user doesn't need it running: report, don't auto-down.
