# Temporal Kilvin Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `explorer/`, a source-grounded Temporal Explorer that teaches how a Kilvin-inspired Python asyncio workflow flows through sdk-python, the bridge, sdk-core, and Temporal server.

**Architecture:** The app is a self-contained Vite/React/TypeScript project copied from the `vllm/explorer` Observatory shell and narrowed to two modes: Lifecycle Deep Dive and Control Paths. Python scripts generate static JSON manifests from curated lifecycle data plus symbol-grep source refs against the initialized local repos. React fetches generated JSON only; it never reads the managed repos at runtime.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind 4, lucide-react, Radix Slot, Python 3.11+ generator tests through `pytest`, and the existing `monoctl` workspace state.

---

## File Structure

- Create `explorer/package.json`, `explorer/vite.config.ts`, `explorer/tsconfig*.json`, `explorer/eslint.config.js`, `explorer/index.html`: Vite app scaffold copied from `~/CodeBase/vllm/explorer` with project name/title updated.
- Create `explorer/src/App.tsx`: Observatory shell with `Lifecycle Deep Dive` and `Control Paths` modes.
- Create `explorer/src/index.css`: Observatory tokens and diagram styles adapted from vLLM; add swimlane and lifecycle node classes.
- Create `explorer/src/explorer-kit/*`, `explorer/src/components/ui/*`, `explorer/src/lib/*`: copied shared UI primitives and fetch/assets helpers.
- Create `explorer/src/lifecycle/types.ts`: TypeScript manifest contract.
- Create `explorer/src/lifecycle/LifecycleExplorer.tsx`: loads lifecycle index/manifest and renders phase controls, diagram, and drawer.
- Create `explorer/src/lifecycle/LifecycleDiagram.tsx`: SVG swimlane diagram, computed node widths, phase highlighting, keyboard selection.
- Create `explorer/src/lifecycle/LifecycleDrawer.tsx`: source-backed detail drawer.
- Create `explorer/src/control/ControlPathsExplorer.tsx`: loads control scenario index/manifests and reuses lifecycle diagram with overlays.
- Create `explorer/scripts/_refs.py`: source-ref resolver and repo metadata helpers.
- Create `explorer/scripts/build_lifecycle_data.py`: emits lifecycle/control-path JSON and `repos.json`.
- Create `explorer/scripts/workflow.sh`: `doctor`, `gen-data`, `install`, `build`, `dev` wrapper.
- Create `tests/explorer/test_lifecycle_data.py`: generator/schema/source-ref tests.
- Modify `Makefile`: add `explorer-gen-data`, `explorer-build`, and `explorer-dev` targets.
- Modify `README.md`: add explorer commands and purpose.

## Task 1: Scaffold Explorer Shell

**Files:**
- Create: `explorer/`
- Create: `explorer/package.json`
- Create: `explorer/vite.config.ts`
- Create: `explorer/tsconfig.json`
- Create: `explorer/tsconfig.app.json`
- Create: `explorer/tsconfig.node.json`
- Create: `explorer/eslint.config.js`
- Create: `explorer/index.html`
- Create: `explorer/public/logo-mark.svg`
- Create: `explorer/src/main.tsx`
- Create: `explorer/src/index.css`
- Create: `explorer/src/explorer-kit/*`
- Create: `explorer/src/components/ui/*`
- Create: `explorer/src/lib/*`
- Create: `explorer/src/App.tsx`

- [ ] **Step 1: Copy the reference app scaffold**

Run:

```bash
mkdir -p explorer
rsync -a \
  --exclude node_modules \
  --exclude dist \
  --exclude public/data \
  --exclude src/data \
  --exclude src/architecture \
  --exclude src/components-deepdive \
  --exclude src/guide \
  /Users/phi9t/CodeBase/vllm/explorer/ explorer/
rm -rf explorer/src/data explorer/src/architecture explorer/src/components-deepdive explorer/src/guide
mkdir -p explorer/public/data
```

Expected: `explorer/package.json`, `explorer/src/App.tsx`, shared kit files, and shared UI files exist.

- [ ] **Step 2: Replace package metadata**

Edit `explorer/package.json` so the project name is Temporal-specific and scripts remain unchanged:

```json
{
  "name": "temporalis-explorer",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "npm run typecheck && vite build",
    "lint": "eslint .",
    "typecheck": "tsc -b",
    "preview": "vite preview"
  }
}
```

Keep all dependency and devDependency entries from the copied `vllm/explorer/package.json`.

- [ ] **Step 3: Replace source URL helpers**

Edit `explorer/src/lib/assets.ts` to:

```ts
export const REPO_HOME = 'https://github.com/phi9t/temporalis'

export function dataUrl(path: string): string {
  const clean = path.replace(/^\//, '')
  return `${import.meta.env.BASE_URL}${clean}`
}

export function logoMarkUrl(): string {
  return dataUrl('logo-mark.svg')
}

export function sourceUrl(repoUrl: string, commit: string, path: string, line?: number): string {
  const anchor = line ? `#L${line}` : ''
  return `${repoUrl.replace(/\.git$/, '')}/blob/${commit}/${path}${anchor}`
}
```

- [ ] **Step 4: Replace `App.tsx` with a two-mode shell**

Edit `explorer/src/App.tsx` to:

```tsx
import { useState } from 'react'
import { ArrowLeft, Network, Route } from 'lucide-react'
import { REPO_HOME, logoMarkUrl } from './lib/assets'
import type { ExplorerMode } from './explorer-kit/mode'
import LifecycleExplorer from './lifecycle/LifecycleExplorer'
import ControlPathsExplorer from './control/ControlPathsExplorer'

const MODES: ExplorerMode[] = [
  {
    id: 'lifecycle',
    label: 'Lifecycle Deep Dive',
    icon: Route,
    subtitle: 'Kilvin-inspired asyncio workflow through Python SDK, bridge, sdk-core, and Temporal server',
    View: LifecycleExplorer,
  },
  {
    id: 'control',
    label: 'Control Paths',
    icon: Network,
    subtitle: 'Retry, replay, pause/resume, heartbeats, cancellation, and sticky workflow cache',
    View: ControlPathsExplorer,
  },
]

export default function App() {
  const [activeId, setActiveId] = useState<string>(MODES[0].id)
  const active = MODES.find((m) => m.id === activeId) ?? MODES[0]
  const ActiveView = active.View

  return (
    <div className="relative min-h-screen">
      <div className="observatory-bg" aria-hidden="true" />
      <div className="explorer-container">
        <header className="explorer-header">
          <div>
            <a href="#main-content" className="skip-link">
              Skip to main content
            </a>
            <a href={REPO_HOME} className="back-home-link" target="_blank" rel="noopener noreferrer">
              <ArrowLeft size={14} aria-hidden="true" />
              <span>phi9t/temporalis</span>
            </a>
            <div className="header-title-row">
              <img src={logoMarkUrl()} alt="" className="header-logo" width={32} height={32} />
              <h1>Temporal Explorer</h1>
            </div>
            <p>{active.subtitle}</p>
          </div>

          <nav className="family-switch" aria-label="Explorer section">
            {MODES.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`family-switch-btn ${activeId === id ? 'active' : ''}`}
                aria-pressed={activeId === id}
                onClick={() => setActiveId(id)}
              >
                <Icon size={14} aria-hidden="true" />
                {label}
              </button>
            ))}
          </nav>
        </header>

        <main id="main-content">
          <ActiveView navigate={setActiveId} />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Add minimal mode components for the first scaffold build**

Create `explorer/src/lifecycle/LifecycleExplorer.tsx`:

```tsx
import type { ExplorerModeProps } from '@/explorer-kit/mode'

export default function LifecycleExplorer(_props: ExplorerModeProps) {
  return <div className="panel p-5 text-sm text-ink-soft">Lifecycle data is generated in Task 2.</div>
}
```

Create `explorer/src/control/ControlPathsExplorer.tsx`:

```tsx
import type { ExplorerModeProps } from '@/explorer-kit/mode'

export default function ControlPathsExplorer(_props: ExplorerModeProps) {
  return <div className="panel p-5 text-sm text-ink-soft">Control path data is generated in Task 2.</div>
}
```

- [ ] **Step 6: Install and verify the scaffold**

Run:

```bash
cd explorer
npm install
npm run typecheck
npm run build
```

Expected: typecheck and build exit 0.

- [ ] **Step 7: Commit**

```bash
git add explorer
git commit -m "Add Temporal explorer scaffold"
```

## Task 2: Build Source-Resolved Lifecycle Manifests

**Files:**
- Create: `explorer/scripts/_refs.py`
- Create: `explorer/scripts/build_lifecycle_data.py`
- Create: `tests/explorer/test_lifecycle_data.py`
- Create generated: `explorer/public/data/lifecycle/index.json`
- Create generated: `explorer/public/data/lifecycle/kilvin-asyncio-happy-path.json`
- Create generated: `explorer/public/data/control-paths/index.json`
- Create generated: `explorer/public/data/control-paths/*.json`
- Create generated: `explorer/public/data/repos.json`

- [ ] **Step 1: Write failing generator tests**

Create `tests/explorer/test_lifecycle_data.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "explorer" / "public" / "data"


def run_generator() -> None:
    subprocess.run(
        [sys.executable, "explorer/scripts/build_lifecycle_data.py", "--repo-root", "."],
        cwd=ROOT,
        check=True,
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_lifecycle_manifest_is_schema_consistent() -> None:
    run_generator()
    manifest = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    node_ids = {node["id"] for node in manifest["nodes"]}
    edge_ids = {(edge["from"], edge["to"]) for edge in manifest["edges"]}

    assert {"kilvin-client", "python-worker", "bridge-worker", "core-worker", "frontend-service", "history-service", "matching-service"} <= node_ids
    assert ("python-worker", "bridge-worker") in edge_ids
    assert ("core-worker", "matching-service") in edge_ids
    for phase in manifest["phases"]:
      assert phase["node_ids"]
      assert set(phase["node_ids"]) <= node_ids


def test_source_refs_resolve_to_real_lines() -> None:
    run_generator()
    manifest = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    refs = [ref for node in manifest["nodes"] for ref in node["refs"]]
    required = {
        ("kilvin", "kilvin-py/worker.py"),
        ("sdk-python", "temporalio/worker/_worker.py"),
        ("sdk-python", "temporalio/bridge/worker.py"),
        ("sdk-core", "crates/sdk-core/src/lib.rs"),
        ("temporal", "service/frontend/workflow_handler.go"),
    }
    got = {(ref["repo"], ref["path"]) for ref in refs}
    assert required <= got
    assert all(isinstance(ref["line"], int) and ref["line"] > 0 for ref in refs)


def test_control_path_overlays_reference_existing_nodes_and_edges() -> None:
    run_generator()
    lifecycle = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    node_ids = {node["id"] for node in lifecycle["nodes"]}
    edge_ids = {edge["id"] for edge in lifecycle["edges"]}
    index = json.loads((OUT / "control-paths" / "index.json").read_text(encoding="utf-8"))
    assert {entry["slug"] for entry in index} == {
        "pause-resume",
        "retry",
        "replay",
        "heartbeat-cancellation",
        "sticky-cache-eviction",
    }
    for entry in index:
        scenario = load_json(OUT / entry["manifest"])
        assert set(scenario["highlight_node_ids"]) <= node_ids
        assert set(scenario["highlight_edge_ids"]) <= edge_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py
```

Expected: FAIL because `explorer/scripts/build_lifecycle_data.py` does not exist.

- [ ] **Step 3: Implement source-ref helpers**

Create `explorer/scripts/_refs.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoInfo:
    id: str
    path: str
    branch: str
    head: str
    remote: str


def load_repos(repo_root: Path) -> dict[str, RepoInfo]:
    raw = json.loads((repo_root / ".monorepo" / "current.lock.json").read_text(encoding="utf-8"))
    repos: dict[str, RepoInfo] = {}
    for repo in raw["repos"]:
        remotes = repo.get("remotes", {})
        origin = remotes.get("origin", "")
        repos[repo["id"]] = RepoInfo(
            id=repo["id"],
            path=repo["path"],
            branch=repo.get("branch") or "detached",
            head=repo["head"],
            remote=origin,
        )
    return repos


def repo_abs_path(repo_root: Path, repo: RepoInfo) -> Path:
    return (repo_root / ".monorepo" / repo.path).resolve()


def github_url(remote: str) -> str:
    if remote.startswith("git@github.com:"):
        return "https://github.com/" + remote.removeprefix("git@github.com:").removesuffix(".git")
    return remote.removesuffix(".git")


def resolve_line(base: Path, rel_path: str, symbol: str) -> int:
    path = base / rel_path
    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        if symbol in line:
            return idx
    raise ValueError(f"symbol {symbol!r} not found in {path}")
```

- [ ] **Step 4: Implement lifecycle generator**

Create `explorer/scripts/build_lifecycle_data.py` with the complete curated dataset and source ref resolution:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from _refs import github_url, load_repos, repo_abs_path, resolve_line


def ref(repo_root: Path, repos, repo_id: str, path: str, symbol: str, label: str) -> dict:
    repo = repos[repo_id]
    return {
        "repo": repo_id,
        "label": label,
        "path": path,
        "line": resolve_line(repo_abs_path(repo_root, repo), path, symbol),
        "symbol": symbol,
        "url": f"{github_url(repo.remote)}/blob/{repo.head}/{path}",
    }


def local_ref(repo_root: Path, path: str, symbol: str, label: str) -> dict:
    return {
        "repo": "kilvin",
        "label": label,
        "path": path,
        "line": resolve_line(repo_root, path, symbol),
        "symbol": symbol,
        "url": f"https://github.com/phi9t/temporalis/blob/phi9t-mainline/{path}",
    }


def edge(edge_id: str, source: str, target: str, kind: str, label: str) -> dict:
    return {"id": edge_id, "from": source, "to": target, "kind": kind, "label": label}


def build(repo_root: Path) -> dict[str, object]:
    repos = load_repos(repo_root)
    nodes = [
        {
            "id": "kilvin-client",
            "label": "Kilvin client",
            "layer": "kilvin",
            "kind": "client",
            "summary": "Starts the parent command workflow with a staged training config.",
            "notes": "The sample config models foundation and post-foundation stages, which gives the walkthrough enough complexity to explain task queues, child workflows, activities, retries, and cleanup.",
            "refs": [local_ref(repo_root, "kilvin-py/start_workflow.py", "ParentCmdWorkflow", "start_workflow.py")],
        },
        {
            "id": "python-worker",
            "label": "Python Worker.run",
            "layer": "sdk-python",
            "kind": "worker",
            "summary": "Runs asyncio poll loops for workflow activations and activity tasks.",
            "notes": "Python owns user-code execution and asyncio scheduling; sdk-core owns task polling, workflow cache, state machines, and server completions.",
            "refs": [
                local_ref(repo_root, "kilvin-py/worker.py", "Worker(", "kilvin worker"),
                ref(repo_root, repos, "sdk-python", "temporalio/worker/_worker.py", "class Worker", "sdk-python Worker"),
                ref(repo_root, repos, "sdk-python", "temporalio/worker/_workflow.py", "async def run", "workflow poll loop"),
                ref(repo_root, repos, "sdk-python", "temporalio/worker/_activity.py", "async def run", "activity poll loop"),
            ],
        },
        {
            "id": "bridge-worker",
            "label": "Bridge worker",
            "layer": "bridge",
            "kind": "bridge",
            "summary": "Serializes Python async calls into sdk-core worker operations.",
            "notes": "The Python bridge exposes poll_workflow_activation, poll_activity_task, completion, and heartbeat calls backed by the Rust C bridge.",
            "refs": [
                ref(repo_root, repos, "sdk-python", "temporalio/bridge/worker.py", "poll_workflow_activation", "Python bridge poll activation"),
                ref(repo_root, repos, "sdk-python", "temporalio/bridge/worker.py", "complete_workflow_activation", "Python bridge complete activation"),
                ref(repo_root, repos, "sdk-core", "crates/sdk-core-c-bridge/src/worker.rs", "temporal_core_worker_poll_workflow_activation", "C bridge poll activation"),
            ],
        },
        {
            "id": "core-runtime",
            "label": "Core runtime",
            "layer": "sdk-core",
            "kind": "runtime",
            "summary": "Hosts the Tokio runtime, telemetry, heartbeat interval, and worker initialization.",
            "notes": "CoreRuntime is created before workers or clients call async core functions so tracing and runtime state are attached correctly.",
            "refs": [ref(repo_root, repos, "sdk-core", "crates/sdk-core/src/lib.rs", "pub struct CoreRuntime", "CoreRuntime")],
        },
        {
            "id": "core-worker",
            "label": "Core worker",
            "layer": "sdk-core",
            "kind": "worker",
            "summary": "Manages pollers, slots, sticky cache, workflow activations, activity tasks, and completions.",
            "notes": "Core converts server workflow-task responses into activations for Python and converts Python completions back into Temporal commands.",
            "refs": [
                ref(repo_root, repos, "sdk-core", "crates/sdk-core/src/lib.rs", "pub fn init_worker", "init_worker"),
                ref(repo_root, repos, "sdk-core", "crates/sdk-core/src/worker/mod.rs", "pub struct WorkerConfig", "WorkerConfig"),
            ],
        },
        {
            "id": "frontend-service",
            "label": "Frontend",
            "layer": "server",
            "kind": "service",
            "summary": "Accepts client RPCs such as starting workflows and completing tasks.",
            "notes": "Frontend is the public gRPC entrypoint and routes workflow operations into History and task polling behavior.",
            "refs": [ref(repo_root, repos, "temporal", "service/frontend/workflow_handler.go", "StartWorkflowExecution", "StartWorkflowExecution")],
        },
        {
            "id": "history-service",
            "label": "History",
            "layer": "server",
            "kind": "history",
            "summary": "Owns durable workflow history and turns commands into new events and tasks.",
            "notes": "History is the source of truth for replay. Workflow progress is event-sourced, not stored in Python process memory.",
            "refs": [ref(repo_root, repos, "temporal", "service/history/handler.go", "RespondWorkflowTaskCompleted", "RespondWorkflowTaskCompleted")],
        },
        {
            "id": "matching-service",
            "label": "Matching",
            "layer": "server",
            "kind": "task-queue",
            "summary": "Matches workflow and activity tasks to polling workers on task queues.",
            "notes": "Matching is why workers poll instead of the server directly invoking user processes.",
            "refs": [ref(repo_root, repos, "temporal", "service/matching/handler.go", "PollWorkflowTaskQueue", "PollWorkflowTaskQueue")],
        },
        {
            "id": "workflow-activation",
            "label": "Activation",
            "layer": "sdk-python",
            "kind": "workflow",
            "summary": "Python receives a WorkflowActivation and resumes deterministic workflow code.",
            "notes": "For the Kilvin-inspired flow, activation drives the parent workflow and child training workflow until they block on commands.",
            "refs": [ref(repo_root, repos, "sdk-python", "temporalio/worker/_workflow.py", "_handle_activation", "_handle_activation")],
        },
        {
            "id": "activity-task",
            "label": "Activity task",
            "layer": "sdk-python",
            "kind": "activity",
            "summary": "Python executes async activities such as resource allocation, bundle materialization, and monitoring.",
            "notes": "Activities perform side effects and heartbeat progress while workflow code remains deterministic.",
            "refs": [
                local_ref(repo_root, "kilvin-py/kilvin_py/activities.py", "async def allocate_resources", "allocate_resources"),
                local_ref(repo_root, "kilvin-py/kilvin_py/activities.py", "async def monitor_training", "monitor_training"),
            ],
        },
    ]
    edges = [
        edge("start-rpc", "kilvin-client", "frontend-service", "rpc", "StartWorkflowExecution"),
        edge("history-start", "frontend-service", "history-service", "history-event", "append WorkflowExecutionStarted"),
        edge("schedule-wft", "history-service", "matching-service", "task-dispatch", "enqueue workflow task"),
        edge("worker-poll", "python-worker", "bridge-worker", "poll", "await poll_workflow_activation"),
        edge("bridge-core", "bridge-worker", "core-worker", "poll", "core poller"),
        edge("core-matching", "core-worker", "matching-service", "poll", "PollWorkflowTaskQueue"),
        edge("activation-up", "core-worker", "workflow-activation", "activation", "WorkflowActivation"),
        edge("activity-command", "workflow-activation", "history-service", "command", "ScheduleActivityTask command"),
        edge("activity-dispatch", "history-service", "matching-service", "task-dispatch", "enqueue activity task"),
        edge("activity-poll", "core-worker", "activity-task", "activation", "ActivityTask"),
        edge("heartbeat", "activity-task", "core-worker", "heartbeat", "RecordHeartbeat"),
        edge("activity-complete", "activity-task", "history-service", "completion", "ActivityTaskCompleted"),
        edge("workflow-complete", "workflow-activation", "history-service", "completion", "RespondWorkflowTaskCompleted"),
    ]
    phases = [
        {"id": "start", "label": "Start workflow", "summary": "Kilvin submits a staged training run.", "node_ids": ["kilvin-client", "frontend-service", "history-service"]},
        {"id": "poll", "label": "Poll task queue", "summary": "Worker polling crosses Python, bridge, core, and Matching.", "node_ids": ["python-worker", "bridge-worker", "core-worker", "matching-service"]},
        {"id": "activate", "label": "Activate workflow", "summary": "Core delivers a workflow activation to Python asyncio code.", "node_ids": ["core-worker", "workflow-activation", "python-worker"]},
        {"id": "schedule-activity", "label": "Schedule activity", "summary": "Workflow commands become durable history events and activity tasks.", "node_ids": ["workflow-activation", "history-service", "matching-service"]},
        {"id": "execute-activity", "label": "Execute activity", "summary": "Python runs side-effecting activity code and heartbeats progress.", "node_ids": ["activity-task", "core-worker", "history-service"]},
        {"id": "complete", "label": "Complete turn", "summary": "Completions update history and may schedule the next workflow task.", "node_ids": ["workflow-activation", "history-service", "matching-service"]},
    ]
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "slug": "kilvin-asyncio-happy-path",
        "label": "Kilvin asyncio happy path",
        "phases": phases,
        "nodes": nodes,
        "edges": edges,
    }


def control_scenarios() -> list[dict]:
    return [
        {"slug": "pause-resume", "label": "Pause / resume", "summary": "Signals change workflow state; replay preserves deterministic history.", "highlight_node_ids": ["workflow-activation", "history-service"], "highlight_edge_ids": ["workflow-complete", "schedule-wft"]},
        {"slug": "retry", "label": "Retry", "summary": "Activity failure appends history and server/core coordinate retry dispatch.", "highlight_node_ids": ["activity-task", "history-service", "matching-service"], "highlight_edge_ids": ["activity-complete", "activity-dispatch"]},
        {"slug": "replay", "label": "Replay", "summary": "History events rebuild workflow state before new commands are accepted.", "highlight_node_ids": ["history-service", "core-worker", "workflow-activation"], "highlight_edge_ids": ["activation-up", "workflow-complete"]},
        {"slug": "heartbeat-cancellation", "label": "Heartbeat cancellation", "summary": "Activity heartbeats let cancellation and progress flow through core.", "highlight_node_ids": ["activity-task", "core-worker", "history-service"], "highlight_edge_ids": ["heartbeat", "activity-complete"]},
        {"slug": "sticky-cache-eviction", "label": "Sticky cache eviction", "summary": "Core cache eviction moves execution back to replay from history.", "highlight_node_ids": ["core-worker", "history-service", "matching-service"], "highlight_edge_ids": ["core-matching", "activation-up"]},
    ]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    out = repo_root / "explorer" / "public" / "data"

    lifecycle = build(repo_root)
    write_json(out / "lifecycle" / "kilvin-asyncio-happy-path.json", lifecycle)
    write_json(out / "lifecycle" / "index.json", [{"slug": lifecycle["slug"], "label": lifecycle["label"], "manifest": "lifecycle/kilvin-asyncio-happy-path.json"}])

    scenarios = control_scenarios()
    write_json(out / "control-paths" / "index.json", [{"slug": s["slug"], "label": s["label"], "manifest": f"control-paths/{s['slug']}.json"} for s in scenarios])
    for scenario in scenarios:
        write_json(out / "control-paths" / f"{scenario['slug']}.json", scenario)

    repos = load_repos(repo_root)
    write_json(out / "repos.json", {repo_id: {"branch": repo.branch, "head": repo.head, "remote": repo.remote, "github": github_url(repo.remote)} for repo_id, repo in sorted(repos.items())})
    print("wrote lifecycle and control-path manifests")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run generator tests**

Run:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py
```

Expected: PASS.

- [ ] **Step 6: Generate data**

Run:

```bash
python explorer/scripts/build_lifecycle_data.py --repo-root .
```

Expected: prints `wrote lifecycle and control-path manifests`.

- [ ] **Step 7: Commit**

```bash
git add explorer/scripts explorer/public/data tests/explorer/test_lifecycle_data.py
git commit -m "Generate Temporal lifecycle manifests"
```

## Task 3: Implement Lifecycle UI

**Files:**
- Create: `explorer/src/lifecycle/types.ts`
- Create: `explorer/src/lifecycle/LifecycleDiagram.tsx`
- Create: `explorer/src/lifecycle/LifecycleDrawer.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add manifest types**

Create `explorer/src/lifecycle/types.ts`:

```ts
export type LayerId = 'kilvin' | 'sdk-python' | 'bridge' | 'sdk-core' | 'server'

export interface SourceRef {
  repo: string
  label: string
  path: string
  line: number
  symbol: string
  url: string
}

export interface LifecycleNode {
  id: string
  label: string
  layer: LayerId
  kind: string
  summary: string
  notes: string
  refs: SourceRef[]
}

export interface LifecycleEdge {
  id: string
  from: string
  to: string
  kind: string
  label: string
}

export interface LifecyclePhase {
  id: string
  label: string
  summary: string
  node_ids: string[]
}

export interface LifecycleManifest {
  generated_at: string
  slug: string
  label: string
  phases: LifecyclePhase[]
  nodes: LifecycleNode[]
  edges: LifecycleEdge[]
}

export interface ControlScenario {
  slug: string
  label: string
  summary: string
  highlight_node_ids: string[]
  highlight_edge_ids: string[]
}
```

- [ ] **Step 2: Add lifecycle diagram**

Create `explorer/src/lifecycle/LifecycleDiagram.tsx`:

```tsx
import { cn } from '@/lib/utils'
import type { LifecycleEdge, LifecycleNode } from './types'

const LAYERS = [
  { id: 'kilvin', label: 'Kilvin app', y: 34 },
  { id: 'sdk-python', label: 'Python SDK', y: 134 },
  { id: 'bridge', label: 'Bridge', y: 234 },
  { id: 'sdk-core', label: 'sdk-core', y: 334 },
  { id: 'server', label: 'Temporal server', y: 434 },
] as const

const X: Record<string, number> = {
  'kilvin-client': 70,
  'python-worker': 70,
  'bridge-worker': 250,
  'core-runtime': 70,
  'core-worker': 250,
  'frontend-service': 70,
  'history-service': 250,
  'matching-service': 430,
  'workflow-activation': 430,
  'activity-task': 610,
}

function nodeWidth(label: string): number {
  return Math.max(132, label.length * 8.2 + 38)
}

function nodeBox(node: LifecycleNode) {
  const layer = LAYERS.find((l) => l.id === node.layer) ?? LAYERS[0]
  const width = nodeWidth(node.label)
  return { x: X[node.id] ?? 70, y: layer.y + 24, width, height: 50, cx: (X[node.id] ?? 70) + width / 2, cy: layer.y + 49 }
}

export default function LifecycleDiagram({
  nodes,
  edges,
  activeNodeIds,
  activeEdgeIds,
  selectedId,
  onSelect,
}: {
  nodes: LifecycleNode[]
  edges: LifecycleEdge[]
  activeNodeIds: Set<string>
  activeEdgeIds: Set<string>
  selectedId: string | null
  onSelect: (node: LifecycleNode) => void
}) {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  return (
    <svg viewBox="0 0 820 560" className="lifecycle-svg" role="group" aria-label="Temporal lifecycle diagram">
      {LAYERS.map((layer) => (
        <g key={layer.id}>
          <rect className="lifecycle-lane" x={12} y={layer.y} width={796} height={92} rx={12} />
          <text className="lifecycle-lane-label" x={26} y={layer.y + 22}>
            {layer.label}
          </text>
        </g>
      ))}
      {edges.map((edge) => {
        const from = byId.get(edge.from)
        const to = byId.get(edge.to)
        if (!from || !to) return null
        const a = nodeBox(from)
        const b = nodeBox(to)
        const active = activeEdgeIds.has(edge.id)
        return (
          <g key={edge.id} className={cn('lifecycle-edge', active && 'active')}>
            <line x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} />
            <title>{edge.label}</title>
          </g>
        )
      })}
      {nodes.map((node) => {
        const box = nodeBox(node)
        const active = activeNodeIds.has(node.id)
        const selected = selectedId === node.id
        return (
          <g
            key={node.id}
            className={cn('lifecycle-node', active && 'active', selected && 'selected')}
            transform={`translate(${box.x},${box.y})`}
            role="button"
            tabIndex={0}
            aria-label={node.label}
            onClick={() => onSelect(node)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onSelect(node)
              }
            }}
          >
            <rect width={box.width} height={box.height} rx={8} />
            <text x={box.width / 2} y={30} textAnchor="middle">
              {node.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
```

- [ ] **Step 3: Add lifecycle drawer**

Create `explorer/src/lifecycle/LifecycleDrawer.tsx`:

```tsx
import { ExternalLink } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { LifecycleNode, LifecyclePhase } from './types'

export default function LifecycleDrawer({
  node,
  phase,
}: {
  node: LifecycleNode | null
  phase: LifecyclePhase | null
}) {
  if (!node) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{phase?.label ?? 'Select a node'}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-ink-soft">
          {phase?.summary ?? 'Choose a lifecycle node to inspect source-backed details.'}
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{node.label}</CardTitle>
        <p className="font-mono text-xs text-cyan">{node.layer} · {node.kind}</p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-ink">{node.summary}</p>
        <p className="text-ink-soft">{node.notes}</p>
        <div>
          <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Source refs</h4>
          <div className="space-y-2">
            {node.refs.map((ref) => (
              <a
                key={`${ref.repo}:${ref.path}:${ref.line}`}
                className="source-link"
                href={`${ref.url}#L${ref.line}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span>{ref.label}</span>
                <span className="font-mono text-[11px] text-ink-muted">{ref.path}:{ref.line}</span>
                <ExternalLink size={12} aria-hidden="true" />
              </a>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 4: Replace lifecycle explorer**

Edit `explorer/src/lifecycle/LifecycleExplorer.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { ViewTabs } from '@/explorer-kit/ViewTabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import LifecycleDiagram from './LifecycleDiagram'
import LifecycleDrawer from './LifecycleDrawer'
import type { LifecycleManifest, LifecycleNode } from './types'

interface LifecycleEntry {
  slug: string
  label: string
  manifest: string
}

export default function LifecycleExplorer(_props: ExplorerModeProps) {
  const [index, setIndex] = useState<LifecycleEntry[] | null>(null)
  const [indexError, setIndexError] = useState<string | null>(null)
  const [slug, setSlug] = useState<string>('')
  const [manifest, setManifest] = useState<LifecycleManifest | null>(null)
  const [manifestError, setManifestError] = useState<string | null>(null)
  const [phaseId, setPhaseId] = useState<string>('')
  const [selected, setSelected] = useState<LifecycleNode | null>(null)

  useEffect(() => {
    fetchExplorerJson<LifecycleEntry[]>('lifecycle/index.json')
      .then((entries) => {
        setIndex(entries)
        setSlug(entries[0]?.slug ?? '')
      })
      .catch((error) => setIndexError(errorMessage(error)))
  }, [])

  const entry = index?.find((item) => item.slug === slug) ?? null

  useEffect(() => {
    if (!entry) return
    setManifest(null)
    setManifestError(null)
    fetchExplorerJson<LifecycleManifest>(entry.manifest)
      .then((loaded) => {
        setManifest(loaded)
        setPhaseId(loaded.phases[0]?.id ?? '')
        setSelected(null)
      })
      .catch((error) => setManifestError(errorMessage(error)))
  }, [entry])

  const phase = manifest?.phases.find((item) => item.id === phaseId) ?? manifest?.phases[0] ?? null
  const activeNodeIds = useMemo(() => new Set(phase?.node_ids ?? []), [phase])
  const activeEdgeIds = useMemo(() => {
    if (!manifest) return new Set<string>()
    return new Set(
      manifest.edges
        .filter((edge) => activeNodeIds.has(edge.from) || activeNodeIds.has(edge.to))
        .map((edge) => edge.id),
    )
  }, [activeNodeIds, manifest])

  if (!index) {
    return <AsyncBoundary loading={indexError === null} error={indexError} loadingLabel="Loading lifecycle index..." errorPrefix="Failed to load lifecycle index" />
  }
  if (!manifest) {
    return <AsyncBoundary loading={manifestError === null} error={manifestError} loadingLabel="Loading lifecycle manifest..." errorPrefix="Failed to load lifecycle manifest" />
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <SubjectSwitcher
          label="Lifecycle"
          ariaLabel="Lifecycle subject"
          value={slug}
          options={index.map((item) => ({ value: item.slug, label: item.label }))}
          onChange={setSlug}
        />
        <ViewTabs
          ariaLabel="Lifecycle phase"
          value={phase?.id ?? ''}
          onChange={setPhaseId}
          options={manifest.phases.map((item) => ({ value: item.id, label: item.label }))}
        />
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
        <Card>
          <CardHeader>
            <CardTitle>{phase?.label ?? manifest.label}</CardTitle>
            <p className="text-sm text-ink-soft">{phase?.summary}</p>
          </CardHeader>
          <CardContent>
            <LifecycleDiagram
              nodes={manifest.nodes}
              edges={manifest.edges}
              activeNodeIds={activeNodeIds}
              activeEdgeIds={activeEdgeIds}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          </CardContent>
        </Card>
        <div className="xl:sticky xl:top-6">
          <LifecycleDrawer node={selected} phase={phase} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Add lifecycle CSS**

Append to `explorer/src/index.css`:

```css
.lifecycle-svg {
  width: 100%;
  max-width: 1120px;
  font-family: var(--font-mono);
}

.lifecycle-lane {
  fill: rgba(15, 23, 42, 0.46);
  stroke: rgba(255, 255, 255, 0.08);
}

.lifecycle-lane-label {
  fill: var(--color-ink-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.lifecycle-edge line {
  stroke: rgba(148, 163, 184, 0.32);
  stroke-width: 1.4;
}

.lifecycle-edge.active line {
  stroke: var(--color-cyan);
  stroke-width: 2.2;
  filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.35));
}

.lifecycle-node {
  cursor: pointer;
  opacity: 0.55;
  outline: none;
}

.lifecycle-node rect {
  fill: rgba(17, 24, 39, 0.94);
  stroke: rgba(99, 102, 241, 0.45);
  stroke-width: 1.4;
}

.lifecycle-node text {
  fill: var(--color-ink);
  font-size: 12px;
  font-weight: 600;
}

.lifecycle-node.active,
.lifecycle-node.selected {
  opacity: 1;
}

.lifecycle-node.selected rect {
  stroke: var(--color-cyan);
  stroke-width: 2.4;
  filter: drop-shadow(0 0 9px rgba(56, 189, 248, 0.4));
}

.lifecycle-node:focus-visible rect {
  stroke: var(--color-cyan);
  stroke-width: 3;
}

.source-link {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border: 1px solid var(--color-panelborder);
  border-radius: var(--radius-btn);
  color: var(--color-ink-soft);
  text-decoration: none;
  background: rgba(15, 23, 42, 0.44);
}

.source-link:hover {
  border-color: var(--color-panelborder-active);
  color: var(--color-cyan);
}

@media (prefers-reduced-motion: reduce) {
  .lifecycle-edge line,
  .lifecycle-node,
  .lifecycle-node rect {
    transition: none;
  }
}
```

- [ ] **Step 6: Verify frontend**

Run:

```bash
cd explorer
npm run typecheck
npm run build
```

Expected: both commands exit 0.

- [ ] **Step 7: Commit**

```bash
git add explorer/src
git commit -m "Add Temporal lifecycle explorer UI"
```

## Task 4: Implement Control Path Overlays

**Files:**
- Modify: `explorer/src/control/ControlPathsExplorer.tsx`
- Modify: `explorer/src/lifecycle/LifecycleDiagram.tsx`

- [ ] **Step 1: Replace control paths explorer**

Edit `explorer/src/control/ControlPathsExplorer.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import LifecycleDiagram from '@/lifecycle/LifecycleDiagram'
import LifecycleDrawer from '@/lifecycle/LifecycleDrawer'
import type { ControlScenario, LifecycleManifest, LifecycleNode } from '@/lifecycle/types'

interface ControlEntry {
  slug: string
  label: string
  manifest: string
}

export default function ControlPathsExplorer(_props: ExplorerModeProps) {
  const [lifecycle, setLifecycle] = useState<LifecycleManifest | null>(null)
  const [index, setIndex] = useState<ControlEntry[] | null>(null)
  const [slug, setSlug] = useState<string>('')
  const [scenario, setScenario] = useState<ControlScenario | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<LifecycleNode | null>(null)

  useEffect(() => {
    Promise.all([
      fetchExplorerJson<LifecycleManifest>('lifecycle/kilvin-asyncio-happy-path.json'),
      fetchExplorerJson<ControlEntry[]>('control-paths/index.json'),
    ])
      .then(([loadedLifecycle, loadedIndex]) => {
        setLifecycle(loadedLifecycle)
        setIndex(loadedIndex)
        setSlug(loadedIndex[0]?.slug ?? '')
      })
      .catch((err) => setError(errorMessage(err)))
  }, [])

  const entry = index?.find((item) => item.slug === slug) ?? null

  useEffect(() => {
    if (!entry) return
    setScenario(null)
    setSelected(null)
    fetchExplorerJson<ControlScenario>(entry.manifest)
      .then(setScenario)
      .catch((err) => setError(errorMessage(err)))
  }, [entry])

  const activeNodeIds = useMemo(() => new Set(scenario?.highlight_node_ids ?? []), [scenario])
  const activeEdgeIds = useMemo(() => new Set(scenario?.highlight_edge_ids ?? []), [scenario])

  if (!lifecycle || !index || !scenario) {
    return <AsyncBoundary loading={error === null} error={error} loadingLabel="Loading control paths..." errorPrefix="Failed to load control paths" />
  }

  return (
    <div className="flex flex-col gap-5">
      <SubjectSwitcher
        label="Control path"
        ariaLabel="Control path"
        value={slug}
        options={index.map((item) => ({ value: item.slug, label: item.label }))}
        onChange={setSlug}
      />
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
        <Card>
          <CardHeader>
            <CardTitle>{scenario.label}</CardTitle>
            <p className="text-sm text-ink-soft">{scenario.summary}</p>
          </CardHeader>
          <CardContent>
            <LifecycleDiagram
              nodes={lifecycle.nodes}
              edges={lifecycle.edges}
              activeNodeIds={activeNodeIds}
              activeEdgeIds={activeEdgeIds}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          </CardContent>
        </Card>
        <div className="xl:sticky xl:top-6">
          <LifecycleDrawer node={selected} phase={null} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify frontend**

Run:

```bash
cd explorer
npm run typecheck
npm run build
```

Expected: both commands exit 0.

- [ ] **Step 3: Commit**

```bash
git add explorer/src/control
git commit -m "Add Temporal control path overlays"
```

## Task 5: Add Workflow Script, Make Targets, And Docs

**Files:**
- Create: `explorer/scripts/workflow.sh`
- Modify: `Makefile`
- Modify: `README.md`
- Create: `explorer/README.md`

- [ ] **Step 1: Add explorer workflow script**

Create `explorer/scripts/workflow.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXPLORER="$ROOT/explorer"

case "${1:-all}" in
  doctor)
    cd "$ROOT"
    ./.monorepo/monoctl doctor
    ;;
  gen-data)
    cd "$ROOT"
    ./.monorepo/monoctl doctor
    python explorer/scripts/build_lifecycle_data.py --repo-root .
    ;;
  install)
    cd "$EXPLORER"
    npm install
    ;;
  build)
    cd "$ROOT"
    ./.monorepo/monoctl doctor
    python explorer/scripts/build_lifecycle_data.py --repo-root .
    cd "$EXPLORER"
    npm run build
    ;;
  dev)
    cd "$EXPLORER"
    npm run dev
    ;;
  all)
    "$0" gen-data
    "$0" install
    "$0" build
    ;;
  *)
    echo "usage: $0 [doctor|gen-data|install|build|dev|all]" >&2
    exit 2
    ;;
esac
```

Run:

```bash
chmod +x explorer/scripts/workflow.sh
```

- [ ] **Step 2: Add Make targets**

Append to `Makefile`:

```make
.PHONY: explorer-gen-data explorer-build explorer-dev

explorer-gen-data:
	./explorer/scripts/workflow.sh gen-data

explorer-build:
	./explorer/scripts/workflow.sh build

explorer-dev:
	./explorer/scripts/workflow.sh dev
```

- [ ] **Step 3: Add root README section**

Append to `README.md`:

```markdown
## Temporal Explorer

`explorer/` is a local React app that explains how a Kilvin-inspired Python asyncio workflow moves through sdk-python, the Python bridge, sdk-core, and Temporal server.

Common commands:

```bash
make explorer-gen-data
make explorer-build
make explorer-dev
```

The generator reads the initialized managed repos and writes static JSON under `explorer/public/data/`. Run `make monorepo-init` and confirm `make monorepo-doctor` passes before regenerating explorer data.
```

- [ ] **Step 4: Add explorer README**

Create `explorer/README.md`:

```markdown
# Temporal Explorer

Interactive Observatory-style explorer for understanding how a Kilvin-inspired Python asyncio workflow runs through Temporal.

## Modes

- Lifecycle Deep Dive: happy-path mental model from client start through server history, task queues, sdk-core polling, Python workflow activation, activity execution, and completions.
- Control Paths: overlays for pause/resume, retry, replay, heartbeat cancellation, and sticky-cache eviction.

## Commands

```bash
./scripts/workflow.sh gen-data
./scripts/workflow.sh install
./scripts/workflow.sh build
./scripts/workflow.sh dev
```
```

- [ ] **Step 5: Verify scripts and docs**

Run:

```bash
./explorer/scripts/workflow.sh gen-data
./explorer/scripts/workflow.sh build
```

Expected: generated data refreshes and frontend build exits 0.

- [ ] **Step 6: Commit**

```bash
git add Makefile README.md explorer/README.md explorer/scripts/workflow.sh
git commit -m "Document Temporal explorer workflow"
```

## Task 6: Final Verification And Manual Review

**Files:**
- No planned source edits unless verification exposes a concrete defect.

- [ ] **Step 1: Run Python tests**

Run:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py tests/test_cli.py tests/test_manifest.py tests/test_git_probe.py tests/test_render.py
```

Expected: all selected tests pass.

- [ ] **Step 2: Run monorepo preflight**

Run:

```bash
./.monorepo/monoctl doctor
```

Expected: exit 0 with no `FAIL:` lines.

- [ ] **Step 3: Run frontend build**

Run:

```bash
./explorer/scripts/workflow.sh build
```

Expected: `npm run typecheck` and `vite build` complete successfully.

- [ ] **Step 4: Run local dev server for visual review**

Run:

```bash
cd explorer
npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a local URL. Open it and verify:

- Lifecycle Deep Dive loads first.
- Phase tabs highlight different nodes and edges.
- Keyboard focus reaches every diagram node.
- Enter and Space select focused nodes.
- Drawer source links point to GitHub blob URLs with line anchors.
- Control Paths scenarios change highlighted overlays.
- No node label visually overflows its rectangle.

- [ ] **Step 5: Commit verification fixes if needed**

If Step 4 exposes a defect, make the smallest code/CSS fix, rerun Steps 1-4, and commit:

```bash
git add explorer tests
git commit -m "Polish Temporal explorer verification issues"
```

- [ ] **Step 6: Report final status**

Include:

- Latest commit hash.
- Test commands and pass/fail results.
- Dev server URL if still running.
- Any known residual limitation, especially if full integration tests outside the explorer remain unrelatedly flaky.
