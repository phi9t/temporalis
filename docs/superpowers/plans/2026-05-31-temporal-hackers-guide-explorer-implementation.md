# Temporal Hacker Guide Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a vLLM-style Temporal hacker guide and `hacks/001_*` teaching probes, then connect the existing explorer phases and control-path overlays to guide sections and runnable scripts.

**Architecture:** `HACKERS_GUIDE.md` becomes the root narrative source. `hacks/NNN_*.py` scripts expose metadata through module constants and provide deterministic offline probes. `explorer/scripts/build_lifecycle_data.py` validates guide anchors and hack metadata while enriching lifecycle/control manifests consumed by the existing React modes.

**Tech Stack:** Markdown, Python 3.11+ scripts/tests, existing monorepo source-ref helpers, React 19, TypeScript, Vitest, Vite.

---

## File Structure

- Create `HACKERS_GUIDE.md`: canonical guide with Kilvin happy path first, then Temporal internals/control paths.
- Create `hacks/001_source_map.py`: source-anchor verification and source-map printout.
- Create `hacks/002_lifecycle_manifest.py`: happy-path manifest walkthrough.
- Create `hacks/003_task_queue_polling.py`: task queue polling source/ref walkthrough.
- Create `hacks/004_history_replay.py`: history/replay source/ref walkthrough.
- Create `hacks/005_control_paths.py`: control-path overlay walkthrough.
- Create `hacks/006_optional_local_run.py`: explicit opt-in local Temporal run stub that degrades cleanly.
- Create `hacks/_common.py`: shared repo-root, JSON loading, metadata, and print helpers.
- Create `tests/hacks/test_hacks.py`: validates default hack metadata and command output.
- Modify `explorer/scripts/build_lifecycle_data.py`: extract guide anchors, read hack metadata, enrich lifecycle/control manifests, write `guide/index.json`.
- Modify `tests/explorer/test_lifecycle_data.py`: assert guide/hack fields and validation consistency.
- Modify `explorer/src/lifecycle/types.ts`: add guide/hack metadata fields.
- Modify `explorer/src/lifecycle/LifecycleDrawer.tsx`: add Read / Run / Inspect panel.
- Modify `explorer/src/lifecycle/LifecycleExplorer.tsx`: pass active phase metadata to drawer/header.
- Modify `explorer/src/control/ControlPathsExplorer.tsx`: render control scenario details and guide/hack links.
- Modify `explorer/src/control/ControlPathsExplorer.test.tsx`: assert guide/hack links and details.
- Create `explorer/src/lifecycle/LifecycleExplorer.test.tsx`: assert lifecycle guide/hack links.
- Modify `explorer/src/index.css`: style guide/hack action links and control details.
- Modify `README.md` and `explorer/README.md`: document guide + hacks workflow.

## Task 1: Add Hacker Guide And Hack Scripts

**Files:**
- Create: `HACKERS_GUIDE.md`
- Create: `hacks/_common.py`
- Create: `hacks/001_source_map.py`
- Create: `hacks/002_lifecycle_manifest.py`
- Create: `hacks/003_task_queue_polling.py`
- Create: `hacks/004_history_replay.py`
- Create: `hacks/005_control_paths.py`
- Create: `hacks/006_optional_local_run.py`
- Create: `tests/hacks/test_hacks.py`

- [ ] **Step 1: Write failing hack tests**

Create `tests/hacks/test_hacks.py`:

```python
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HACKS = ROOT / "hacks"
DEFAULT_HACKS = [
    "001_source_map.py",
    "002_lifecycle_manifest.py",
    "003_task_queue_polling.py",
    "004_history_replay.py",
    "005_control_paths.py",
]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_hacks_have_metadata() -> None:
    for name in DEFAULT_HACKS:
        module = load_module(HACKS / name)
        assert isinstance(module.GUIDE_ANCHOR, str)
        assert module.GUIDE_ANCHOR
        assert isinstance(module.SUMMARY, str)
        assert module.SUMMARY


def test_default_hacks_run_and_print_expected_markers() -> None:
    expected = {
        "001_source_map.py": "Temporal source map",
        "002_lifecycle_manifest.py": "Kilvin asyncio happy path",
        "003_task_queue_polling.py": "Task queue polling",
        "004_history_replay.py": "History and replay",
        "005_control_paths.py": "Control paths",
    }
    for name, marker in expected.items():
        completed = subprocess.run(
            [sys.executable, str(HACKS / name)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        assert marker in completed.stdout
```

- [ ] **Step 2: Run hack tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest -q tests/hacks/test_hacks.py
```

Expected: FAIL because `hacks/` does not exist.

- [ ] **Step 3: Add the root hacker guide**

Create `HACKERS_GUIDE.md` with the following required headings and anchors. Use Markdown heading text exactly so generated anchors are stable:

```markdown
# Temporal Hacker's Guide

> A code-first guide to how a Kilvin-inspired Python asyncio workflow moves through sdk-python, the Python bridge, sdk-core, and the Temporal server. Read the happy path first; the advanced control paths are extensions of that same event-sourced loop.

## 1. How to read this guide

Start with the Kilvin running example, then follow each section's source map and `hacks/NNN_*.py` probe. The scripts are intentionally small and mostly offline: they inspect generated explorer manifests and source-grounded refs instead of requiring a live Temporal cluster.

## 2. 30-second architecture

Temporal has four boundaries that matter for this guide: the Python client/worker surface, the Python bridge, sdk-core, and the server. The server owns durable workflow identity, History, Matching, timers, and retry scheduling. sdk-core owns worker polling, workflow cache, activations, completions, activity heartbeats, and replay mediation. sdk-python owns user-code scheduling on asyncio and converts Python workflow/activity code into bridge calls.

## 3. Running example: Kilvin-inspired training workflow

The running example is a parent workflow that starts a staged training run, schedules activities for resource allocation and workload materialization, starts or coordinates child work, monitors progress through a heartbeating activity, and cleans up resources. It is intentionally richer than a greeting workflow because it exposes task queues, child workflows, retries, heartbeats, cancellation, pause/resume, and replay.

## 4. Happy path: start workflow to first activation

User-level event: Kilvin calls the Python client to start a workflow. Temporal boundary: `StartWorkflowExecution` crosses from client into Frontend. Server ownership: Frontend validates and routes the request, History appends the start event and schedules the first workflow task, Matching makes that task available on a task queue. sdk-core ownership: a worker poller receives the task and builds a workflow activation. Python ownership: sdk-python resumes workflow code until it emits commands or blocks.

Try it: `python hacks/002_lifecycle_manifest.py`

## 5. Workflow task polling: Matching -> sdk-core -> bridge -> Python

User-level event: a Python worker appears to await work. Temporal boundary: the worker crosses poll and completion APIs. sdk-core ownership: pollers, slots, workflow-task responses, activations, completion translation, and sticky-cache decisions. Server ownership: Matching hands out workflow tasks and History accepts completions. Deterministic contract: Python workflow code must make the same decisions when replayed from the same history.

Try it: `python hacks/003_task_queue_polling.py`

## 6. Activity execution and heartbeats

Activities are side-effecting work. The workflow schedules an activity command; History records activity task scheduling; Matching dispatches the activity task; sdk-core polls and sends it through the bridge; sdk-python runs the async activity. Heartbeats are progress and cancellation checkpoints owned by activity code at the user level and mediated by sdk-core/server state underneath.

Try it: `python hacks/002_lifecycle_manifest.py`

## 7. History as source of truth and replay

History is the durable log. Workflow memory is a cache, not the source of truth. On replay, sdk-core feeds history back into the workflow state machines and sdk-python re-executes deterministic workflow code to rebuild state before accepting new commands. Activities do not replay their side effects; their completed results are read from history.

Try it: `python hacks/004_history_replay.py`

## 8. Retry and failure handling

Activity failures, timeouts, and worker crashes become durable history decisions. The server records failure events and schedules retries when policy allows. sdk-core reports task outcomes and later polls retry tasks. Python code sees either successful results, retry exhaustion, cancellation, or workflow-task failure depending on where the failure occurs.

Try it: `python hacks/005_control_paths.py`

## 9. Pause/resume as signal/update-driven coordination

Pause/resume is workflow state, not process state. A signal or update records intent in history, workflow code observes it during activation, and future commands reflect the new state. Replay must rebuild the same pause state from history before the workflow continues.

Try it: `python hacks/005_control_paths.py`

## 10. Sticky workflow cache and eviction

Sticky execution lets sdk-core keep workflow state warm for a worker. Eviction is safe because History remains authoritative. On a sticky miss or cache eviction, core rebuilds state through replay and then delivers the next activation to Python.

Try it: `python hacks/005_control_paths.py`

## 11. Where to inspect source next

Use the explorer's source refs for exact line anchors. Start with Kilvin's client and worker files, then sdk-python worker loops, bridge worker calls, sdk-core worker initialization and pollers, and Temporal server Frontend, History, and Matching handlers.

Try it: `python hacks/001_source_map.py`

## 12. Hands-on hacks

Run `python hacks/001_source_map.py` first, then `002`, `003`, `004`, and `005`. `006_optional_local_run.py` is opt-in and should not be part of default verification.
```

- [ ] **Step 4: Add shared hack helpers**

Create `hacks/_common.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "explorer" / "public" / "data"


def load_json(relative: str) -> Any:
    return json.loads((DATA / relative).read_text(encoding="utf-8"))


def print_header(title: str) -> None:
    print(f"== {title} ==")


def iter_refs() -> list[dict[str, Any]]:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    return [ref for node in manifest["nodes"] for ref in node["refs"]]


def print_ref(ref: dict[str, Any]) -> None:
    print(f"- {ref['repo']}:{ref['path']}:{ref['line']} ({ref['label']})")
```

- [ ] **Step 5: Add `001_source_map.py`**

Create `hacks/001_source_map.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

from _common import iter_refs, print_header, print_ref

GUIDE_ANCHOR = "where-to-inspect-source-next"
SUMMARY = "Print the source anchors used by the Temporal guide and explorer."


def main() -> None:
    print_header("Temporal source map")
    for ref in iter_refs():
        print_ref(ref)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Add `002_lifecycle_manifest.py`**

Create `hacks/002_lifecycle_manifest.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "happy-path-start-workflow-to-first-activation"
SUMMARY = "Walk the Kilvin asyncio happy-path lifecycle manifest in phase order."


def main() -> None:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    print_header(manifest["label"])
    nodes = {node["id"]: node["label"] for node in manifest["nodes"]}
    for phase in manifest["phases"]:
        labels = ", ".join(nodes[node_id] for node_id in phase["node_ids"])
        print(f"- {phase['label']}: {labels}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Add `003_task_queue_polling.py`**

Create `hacks/003_task_queue_polling.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "workflow-task-polling-matching---sdk-core---bridge---python"
SUMMARY = "Trace Matching -> sdk-core -> bridge -> Python workflow-task polling."

POLLING_NODES = {"python-worker", "bridge-worker", "core-worker", "matching-service"}


def main() -> None:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    print_header("Task queue polling")
    for node in manifest["nodes"]:
        if node["id"] not in POLLING_NODES:
            continue
        print(f"- {node['label']}: {node['summary']}")
        for ref in node["refs"]:
            print(f"  source: {ref['repo']}:{ref['path']}:{ref['line']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Add `004_history_replay.py`**

Create `hacks/004_history_replay.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "history-as-source-of-truth-and-replay"
SUMMARY = "Show how History, sdk-core, and Python activation refs explain replay."

REPLAY_NODES = {"history-service", "core-worker", "workflow-activation"}


def main() -> None:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    print_header("History and replay")
    for node in manifest["nodes"]:
        if node["id"] in REPLAY_NODES:
            print(f"- {node['label']}: {node['notes']}")
    print("Replay rule: workflow code re-executes deterministically; activity side effects do not.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Add `005_control_paths.py`**

Create `hacks/005_control_paths.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "retry-and-failure-handling"
SUMMARY = "Print control-path overlays for retry, replay, pause/resume, heartbeat cancellation, and sticky eviction."


def main() -> None:
    print_header("Control paths")
    index = load_json("control-paths/index.json")
    for entry in index:
        scenario = load_json(entry["manifest"])
        print(f"- {scenario['label']}: {scenario['summary']}")
        for detail in scenario.get("details", []):
            print(f"  detail: {detail}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 10: Add opt-in local run script**

Create `hacks/006_optional_local_run.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

GUIDE_ANCHOR = "hands-on-hacks"
SUMMARY = "Optional heavier local Temporal run; skipped unless TEMPORALIS_RUN_OPTIONAL_HACK=1."


def main() -> int:
    if os.environ.get("TEMPORALIS_RUN_OPTIONAL_HACK") != "1":
        print("Optional local run skipped. Set TEMPORALIS_RUN_OPTIONAL_HACK=1 to opt in.")
        return 0
    print("Optional local Temporal run is intentionally explicit; wire this to the local runtime when needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 11: Make hack scripts executable and run tests**

Run:

```bash
chmod +x hacks/001_source_map.py hacks/002_lifecycle_manifest.py hacks/003_task_queue_polling.py hacks/004_history_replay.py hacks/005_control_paths.py hacks/006_optional_local_run.py
PYTHONPATH=. pytest -q tests/hacks/test_hacks.py
```

Expected: PASS.

- [ ] **Step 12: Commit Task 1**

Run:

```bash
git add HACKERS_GUIDE.md hacks tests/hacks/test_hacks.py
git commit -m "Add Temporal hacker guide and hacks"
```

## Task 2: Enrich Generated Manifests With Guide And Hack Metadata

**Files:**
- Modify: `explorer/scripts/build_lifecycle_data.py`
- Modify: `tests/explorer/test_lifecycle_data.py`
- Generated: `explorer/public/data/lifecycle/kilvin-asyncio-happy-path.json`
- Generated: `explorer/public/data/control-paths/*.json`
- Generated: `explorer/public/data/guide/index.json`

- [ ] **Step 1: Add failing generator tests for guide/hack metadata**

Append to `tests/explorer/test_lifecycle_data.py`:

```python

def test_guide_index_contains_required_anchors() -> None:
    run_generator()
    guide = json.loads((OUT / "guide" / "index.json").read_text(encoding="utf-8"))
    anchors = {entry["anchor"] for entry in guide["sections"]}
    assert {
        "happy-path-start-workflow-to-first-activation",
        "workflow-task-polling-matching---sdk-core---bridge---python",
        "history-as-source-of-truth-and-replay",
        "retry-and-failure-handling",
        "pause-resume-as-signalupdate-driven-coordination",
        "sticky-workflow-cache-and-eviction",
    } <= anchors


def test_lifecycle_phases_have_guide_and_hack_links() -> None:
    run_generator()
    manifest = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    for phase in manifest["phases"]:
        assert phase["guide_anchor"]
        assert phase["guide_title"]
        assert phase["hack_script"].startswith("hacks/")
        assert phase["hack_script"].endswith(".py")
        assert phase["hack_summary"]


def test_control_scenarios_have_guide_hack_links_and_details() -> None:
    run_generator()
    index = json.loads((OUT / "control-paths" / "index.json").read_text(encoding="utf-8"))
    for entry in index:
        scenario = load_json(OUT / entry["manifest"])
        assert scenario["guide_anchor"]
        assert scenario["guide_title"]
        assert scenario["hack_script"].startswith("hacks/")
        assert scenario["hack_summary"]
        assert len(scenario["details"]) >= 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py
```

Expected: FAIL because guide metadata is not generated yet.

- [ ] **Step 3: Add guide anchor and hack metadata helpers**

Edit `explorer/scripts/build_lifecycle_data.py` and add imports:

```python
import ast
import re
```

Add helper functions below `lock_generated_at`:

```python
def slugify_heading(text: str) -> str:
    text = text.lower()
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def guide_sections(repo_root: Path) -> dict[str, str]:
    path = repo_root / "HACKERS_GUIDE.md"
    sections: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("## "):
            continue
        title = line.removeprefix("## ").strip()
        anchor = slugify_heading(title)
        sections[anchor] = title
    return sections


def read_hack_metadata(repo_root: Path) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for path in sorted((repo_root / "hacks").glob("[0-9][0-9][0-9]_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        values: dict[str, str] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            if node.targets[0].id not in {"GUIDE_ANCHOR", "SUMMARY"}:
                continue
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                continue
            values[node.targets[0].id] = node.value.value
        if "GUIDE_ANCHOR" in values and "SUMMARY" in values:
            metadata[f"hacks/{path.name}"] = {
                "guide_anchor": values["GUIDE_ANCHOR"],
                "hack_summary": values["SUMMARY"],
            }
    return metadata


def guide_link(repo_root: Path, guide: dict[str, str], hacks: dict[str, dict[str, str]], anchor: str, script: str) -> dict[str, str]:
    if anchor not in guide:
        raise ValueError(f"guide anchor {anchor!r} missing from HACKERS_GUIDE.md")
    if script not in hacks:
        raise ValueError(f"hack script {script!r} missing metadata")
    if hacks[script]["guide_anchor"] != anchor:
        raise ValueError(f"{script} points to {hacks[script]['guide_anchor']!r}, expected {anchor!r}")
    if not (repo_root / script).exists():
        raise ValueError(f"hack script {script!r} does not exist")
    return {
        "guide_anchor": anchor,
        "guide_title": guide[anchor],
        "hack_script": script,
        "hack_summary": hacks[script]["hack_summary"],
    }
```

- [ ] **Step 4: Add lifecycle phase metadata**

In `build(repo_root)`, after `repos = load_repos(repo_root)`, add:

```python
    guide = guide_sections(repo_root)
    hacks = read_hack_metadata(repo_root)
```

Replace the `phases = [...]` block with:

```python
    phases = [
        {
            "id": "start",
            "label": "Start workflow",
            "summary": "Kilvin submits a staged training run.",
            "node_ids": ["kilvin-client", "frontend-service", "history-service"],
            **guide_link(repo_root, guide, hacks, "happy-path-start-workflow-to-first-activation", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "poll",
            "label": "Poll task queue",
            "summary": "Worker polling crosses Python, bridge, core, and Matching.",
            "node_ids": ["python-worker", "bridge-worker", "core-worker", "matching-service"],
            **guide_link(repo_root, guide, hacks, "workflow-task-polling-matching---sdk-core---bridge---python", "hacks/003_task_queue_polling.py"),
        },
        {
            "id": "activate",
            "label": "Activate workflow",
            "summary": "Core delivers a workflow activation to Python asyncio code.",
            "node_ids": ["core-worker", "workflow-activation", "python-worker"],
            **guide_link(repo_root, guide, hacks, "workflow-task-polling-matching---sdk-core---bridge---python", "hacks/003_task_queue_polling.py"),
        },
        {
            "id": "schedule-activity",
            "label": "Schedule activity",
            "summary": "Workflow commands become durable history events and activity tasks.",
            "node_ids": ["workflow-activation", "history-service", "matching-service"],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "execute-activity",
            "label": "Execute activity",
            "summary": "Python runs side-effecting activity code and heartbeats progress.",
            "node_ids": ["activity-task", "core-worker", "history-service"],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/002_lifecycle_manifest.py"),
        },
        {
            "id": "complete",
            "label": "Complete turn",
            "summary": "Completions update history and may schedule the next workflow task.",
            "node_ids": ["workflow-activation", "history-service", "matching-service"],
            **guide_link(repo_root, guide, hacks, "history-as-source-of-truth-and-replay", "hacks/004_history_replay.py"),
        },
    ]
```

- [ ] **Step 5: Add control scenario metadata and details**

Change `control_scenarios()` to accept guide metadata:

```python
def control_scenarios(repo_root: Path, guide: dict[str, str], hacks: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
```

Replace the return list with:

```python
    return [
        {
            "slug": "pause-resume",
            "label": "Pause / resume",
            "summary": "Signals or updates change durable workflow state; replay rebuilds the same pause decision before the workflow continues.",
            "highlight_node_ids": ["workflow-activation", "history-service"],
            "highlight_edge_ids": ["workflow-complete", "schedule-wft"],
            "details": [
                "Python workflow code records pause state through deterministic workflow state.",
                "History stores signal or update events so the decision survives worker restarts.",
                "sdk-core replays the event history before delivering a new activation.",
            ],
            **guide_link(repo_root, guide, hacks, "pause-resume-as-signalupdate-driven-coordination", "hacks/005_control_paths.py"),
        },
        {
            "slug": "retry",
            "label": "Retry",
            "summary": "Activity failure is recorded durably, then server retry policy and worker polling produce the next attempt.",
            "highlight_node_ids": ["activity-task", "history-service", "matching-service"],
            "highlight_edge_ids": ["activity-complete", "activity-dispatch"],
            "details": [
                "The Python activity reports failure, timeout, or cancellation through sdk-core.",
                "History records the outcome and computes retry scheduling from policy.",
                "Matching dispatches the next activity task when the retry is due.",
            ],
            **guide_link(repo_root, guide, hacks, "retry-and-failure-handling", "hacks/005_control_paths.py"),
        },
        {
            "slug": "replay",
            "label": "Replay",
            "summary": "History events rebuild workflow state before new commands are accepted.",
            "highlight_node_ids": ["history-service", "core-worker", "workflow-activation"],
            "highlight_edge_ids": ["activation-up", "workflow-complete"],
            "details": [
                "History is the authoritative log of prior workflow decisions.",
                "sdk-core rebuilds workflow state machines from that log.",
                "sdk-python re-executes deterministic workflow code without re-running activity side effects.",
            ],
            **guide_link(repo_root, guide, hacks, "history-as-source-of-truth-and-replay", "hacks/004_history_replay.py"),
        },
        {
            "slug": "heartbeat-cancellation",
            "label": "Heartbeat cancellation",
            "summary": "Activity heartbeats carry progress and provide cancellation checkpoints across Python, sdk-core, and server state.",
            "highlight_node_ids": ["activity-task", "core-worker", "history-service"],
            "highlight_edge_ids": ["heartbeat", "activity-complete"],
            "details": [
                "The Python activity heartbeats while performing side effects.",
                "sdk-core forwards heartbeat state and observes cancellation delivery.",
                "The server tracks cancellation/progress state for the activity attempt.",
            ],
            **guide_link(repo_root, guide, hacks, "activity-execution-and-heartbeats", "hacks/005_control_paths.py"),
        },
        {
            "slug": "sticky-cache-eviction",
            "label": "Sticky cache eviction",
            "summary": "Core cache eviction falls back to replay because History, not worker memory, is authoritative.",
            "highlight_node_ids": ["core-worker", "history-service", "matching-service"],
            "highlight_edge_ids": ["core-matching", "activation-up"],
            "details": [
                "sdk-core may keep workflow state warm in a sticky cache.",
                "Eviction or sticky miss sends execution back through history replay.",
                "Python receives a rebuilt activation after core catches up to the latest history.",
            ],
            **guide_link(repo_root, guide, hacks, "sticky-workflow-cache-and-eviction", "hacks/005_control_paths.py"),
        },
    ]
```

Update `main()` to build guide/hack metadata once:

```python
    guide = guide_sections(repo_root)
    hacks = read_hack_metadata(repo_root)
```

Change scenario generation to:

```python
    scenarios = control_scenarios(repo_root, guide, hacks)
```

- [ ] **Step 6: Write guide index JSON**

In `main()`, before writing `repos.json`, add:

```python
    write_json(
        out / "guide" / "index.json",
        {
            "guide": "HACKERS_GUIDE.md",
            "sections": [{"anchor": anchor, "title": title} for anchor, title in sorted(guide.items())],
            "hacks": [{"script": script, **meta} for script, meta in sorted(hacks.items())],
        },
    )
```

- [ ] **Step 7: Run generator and tests**

Run:

```bash
python explorer/scripts/build_lifecycle_data.py --repo-root .
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py tests/hacks/test_hacks.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add explorer/scripts/build_lifecycle_data.py explorer/public/data tests/explorer/test_lifecycle_data.py
git commit -m "Connect Temporal manifests to guide and hacks"
```

## Task 3: Add Guide/Hack Links To Explorer UI

**Files:**
- Modify: `explorer/src/lifecycle/types.ts`
- Modify: `explorer/src/lifecycle/LifecycleDrawer.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.tsx`
- Modify: `explorer/src/control/ControlPathsExplorer.tsx`
- Modify: `explorer/src/control/ControlPathsExplorer.test.tsx`
- Create: `explorer/src/lifecycle/LifecycleExplorer.test.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add frontend tests for lifecycle guide/hack links**

Create `explorer/src/lifecycle/LifecycleExplorer.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import LifecycleExplorer from './LifecycleExplorer'
import type { LifecycleManifest } from './types'

vi.mock('@/lib/fetch', () => ({
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  fetchExplorerJson: vi.fn(async (path: string) => {
    const data: Record<string, unknown> = {
      'lifecycle/index.json': [
        { slug: 'kilvin-asyncio-happy-path', label: 'Kilvin asyncio happy path', manifest: 'lifecycle/kilvin-asyncio-happy-path.json' },
      ],
      'lifecycle/kilvin-asyncio-happy-path.json': manifest,
    }
    const value = data[path]
    if (!value) throw new Error(`unexpected path ${path}`)
    return value
  }),
}))

const manifest: LifecycleManifest = {
  generated_at: '2026-05-31T00:00:00Z',
  slug: 'kilvin-asyncio-happy-path',
  label: 'Kilvin asyncio happy path',
  phases: [
    {
      id: 'start',
      label: 'Start workflow',
      summary: 'Kilvin submits a staged training run.',
      node_ids: ['kilvin-client'],
      guide_anchor: 'happy-path-start-workflow-to-first-activation',
      guide_title: '4. Happy path: start workflow to first activation',
      hack_script: 'hacks/002_lifecycle_manifest.py',
      hack_summary: 'Walk the Kilvin asyncio happy-path lifecycle manifest in phase order.',
    },
  ],
  nodes: [
    {
      id: 'kilvin-client',
      label: 'Kilvin client',
      layer: 'kilvin',
      kind: 'client',
      summary: 'Starts the workflow.',
      notes: 'Client start crosses Frontend.',
      refs: [],
    },
  ],
  edges: [],
}

describe('LifecycleExplorer', () => {
  it('renders phase guide and hack links', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Read / Run / Inspect')).toBeTruthy()
    })

    expect(screen.getByRole('link', { name: /4\\. Happy path/ }).getAttribute('href')).toBe('/HACKERS_GUIDE.md#happy-path-start-workflow-to-first-activation')
    expect(screen.getByText('python hacks/002_lifecycle_manifest.py')).toBeTruthy()
    expect(screen.getByText('Walk the Kilvin asyncio happy-path lifecycle manifest in phase order.')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Extend control-path UI test**

In `explorer/src/control/ControlPathsExplorer.test.tsx`, replace `scenario` with:

```tsx
const scenario: ControlScenario = {
  slug: 'pause-resume',
  label: 'Pause / resume',
  summary: 'Signals change workflow state; replay preserves deterministic history.',
  highlight_node_ids: ['workflow-activation', 'history-service'],
  highlight_edge_ids: ['workflow-complete'],
  guide_anchor: 'pause-resume-as-signalupdate-driven-coordination',
  guide_title: '9. Pause/resume as signal/update-driven coordination',
  hack_script: 'hacks/005_control_paths.py',
  hack_summary: 'Print control-path overlays.',
  details: [
    'Python workflow code records pause state.',
    'History stores signal or update events.',
    'sdk-core replays history before the next activation.',
  ],
}
```

Add assertions after the existing summary assertion:

```tsx
    expect(screen.getByRole('link', { name: /9\\. Pause\\/resume/ }).getAttribute('href')).toBe('/HACKERS_GUIDE.md#pause-resume-as-signalupdate-driven-coordination')
    expect(screen.getByText('python hacks/005_control_paths.py')).toBeTruthy()
    expect(screen.getByText('sdk-core replays history before the next activation.')).toBeTruthy()
```

- [ ] **Step 3: Run frontend tests to verify failure**

Run:

```bash
cd explorer
npm test
```

Expected: FAIL because types and UI do not render guide/hack metadata.

- [ ] **Step 4: Update TypeScript manifest types**

Edit `explorer/src/lifecycle/types.ts` and add:

```ts
export interface GuideHackLink {
  guide_anchor: string
  guide_title: string
  hack_script: string
  hack_summary: string
}
```

Change `LifecyclePhase` to:

```ts
export interface LifecyclePhase extends GuideHackLink {
  id: string
  label: string
  summary: string
  node_ids: string[]
}
```

Change `ControlScenario` to:

```ts
export interface ControlScenario extends GuideHackLink {
  slug: string
  label: string
  summary: string
  details: string[]
  highlight_node_ids: string[]
  highlight_edge_ids: string[]
}
```

- [ ] **Step 5: Add guide URL helper**

Edit `explorer/src/lib/assets.ts` and add:

```ts
export function guideUrl(anchor: string): string {
  return `${import.meta.env.BASE_URL}HACKERS_GUIDE.md#${anchor}`
}
```

- [ ] **Step 6: Add Read / Run / Inspect panel to lifecycle drawer**

Edit `explorer/src/lifecycle/LifecycleDrawer.tsx`:

1. Change imports:

```tsx
import { BookOpen, ExternalLink, Terminal } from 'lucide-react'
import { guideUrl } from '@/lib/assets'
```

2. Add this helper component above `LifecycleDrawer`:

```tsx
function GuideHackPanel({ phase }: { phase: LifecyclePhase | null }) {
  if (!phase) return null

  return (
    <div className="guide-hack-panel">
      <h4 className="font-mono text-xs uppercase text-ink-muted">Read / Run / Inspect</h4>
      <a className="guide-action" href={guideUrl(phase.guide_anchor)} target="_blank" rel="noopener noreferrer">
        <BookOpen size={13} aria-hidden="true" />
        <span>{phase.guide_title}</span>
      </a>
      <div className="guide-command">
        <Terminal size={13} aria-hidden="true" />
        <code>python {phase.hack_script}</code>
      </div>
      <p className="text-xs text-ink-soft">{phase.hack_summary}</p>
    </div>
  )
}
```

3. In the empty drawer `CardContent`, replace the content with:

```tsx
          <div className="space-y-4">
            <p>{phase?.summary ?? 'Choose a lifecycle node to inspect source-backed details.'}</p>
            <p>Read the current phase, run its paired hack, then inspect a node for source refs.</p>
            <GuideHackPanel phase={phase} />
          </div>
```

4. In the node drawer `CardContent`, add `<GuideHackPanel phase={phase} />` before the source refs block.

- [ ] **Step 7: Render control scenario details and guide/hack links**

Edit `explorer/src/control/ControlPathsExplorer.tsx`:

1. Add imports:

```tsx
import { BookOpen, Terminal } from 'lucide-react'
import { guideUrl } from '@/lib/assets'
```

2. Inside `CardHeader`, after the scenario summary paragraph, add:

```tsx
            <div className="guide-hack-panel compact">
              <a className="guide-action" href={guideUrl(scenario.guide_anchor)} target="_blank" rel="noopener noreferrer">
                <BookOpen size={13} aria-hidden="true" />
                <span>{scenario.guide_title}</span>
              </a>
              <div className="guide-command">
                <Terminal size={13} aria-hidden="true" />
                <code>python {scenario.hack_script}</code>
              </div>
              <p className="text-xs text-ink-soft">{scenario.hack_summary}</p>
            </div>
```

3. Inside `CardContent`, before `LifecycleDiagram`, add:

```tsx
            <ul className="control-details">
              {scenario.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
```

- [ ] **Step 8: Add guide/hack CSS**

Append to `explorer/src/index.css`:

```css
.guide-hack-panel {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--color-panelborder);
  border-radius: var(--radius-btn);
  background: rgba(15, 23, 42, 0.42);
}

.guide-hack-panel.compact {
  margin-top: 12px;
}

.guide-action,
.guide-command {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--color-ink-soft);
}

.guide-action {
  text-decoration: none;
}

.guide-action:hover {
  color: var(--color-cyan);
}

.guide-command code {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 11px;
  color: var(--color-ink);
}

.control-details {
  margin: 0 0 18px;
  padding-left: 18px;
  color: var(--color-ink-soft);
  font-size: 13px;
}

.control-details li + li {
  margin-top: 6px;
}
```

- [ ] **Step 9: Run frontend verification**

Run:

```bash
cd explorer
npm test
npm run typecheck
npm run build
```

Expected: all pass.

- [ ] **Step 10: Commit Task 3**

Run:

```bash
git add explorer/src
git commit -m "Add guide and hack links to Temporal explorer"
```

## Task 4: Docs, Workflow Verification, And Final Commit Hygiene

**Files:**
- Modify: `README.md`
- Modify: `explorer/README.md`

- [ ] **Step 1: Update root README**

Append or update the Temporal Explorer section in `README.md` with:

````markdown
## Temporal Hacker Guide And Explorer

Start with [`HACKERS_GUIDE.md`](HACKERS_GUIDE.md) for the narrative walkthrough. The guide pairs each deep dive with a deterministic script under `hacks/`.

Common commands:

```bash
python hacks/001_source_map.py
python hacks/002_lifecycle_manifest.py
make explorer-gen-data
make explorer-build
make explorer-dev
```

The default hacks and explorer generator do not require a running Temporal server. `hacks/006_optional_local_run.py` is explicit opt-in.
````

- [ ] **Step 2: Update explorer README**

Replace `explorer/README.md` with:

````markdown
# Temporal Explorer

Interactive Observatory-style explorer for understanding how a Kilvin-inspired Python asyncio workflow runs through Temporal.

The explorer is backed by the root [`../HACKERS_GUIDE.md`](../HACKERS_GUIDE.md) and paired scripts under [`../hacks/`](../hacks/). Lifecycle phases and control-path overlays link to the matching guide section, hack command, and source refs.

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
````

- [ ] **Step 3: Run full verification**

Run:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py tests/hacks/test_hacks.py tests/test_cli.py tests/test_manifest.py tests/test_git_probe.py tests/test_render.py
./.monorepo/monoctl doctor
cd explorer && npm test
cd explorer && npm run lint
cd .. && ./explorer/scripts/workflow.sh build
git status --short
```

Expected:

- Pytest exits 0.
- `monoctl doctor` exits 0 with no `FAIL:` lines.
- `npm test` exits 0.
- `npm run lint` exits 0.
- `workflow.sh build` exits 0 after generator/typecheck/Vite build.
- `git status --short` shows only intended README or generated-data changes before commit.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add README.md explorer/README.md explorer/public/data
git commit -m "Document Temporal hacker guide workflow"
```

- [ ] **Step 5: Final status report**

Report:

- Latest commit hash.
- Whether the working tree is clean.
- Exact verification commands and results.
- Any residual limitation, especially that `006_optional_local_run.py` remains opt-in and does not execute a real Temporal run by default.

## Self-Review

- Spec coverage: The plan covers root guide, zero-padded hacks, default-off optional local run, guide anchor extraction, hack metadata extraction, lifecycle/control manifest enrichment, existing explorer mode modification, tests, docs, and final verification.
- Placeholder scan: No task uses TBD/TODO/fill-in language. Each code-editing step provides exact file paths and concrete code blocks.
- Type consistency: `guide_anchor`, `guide_title`, `hack_script`, `hack_summary`, and `details` match across Python generator output, TypeScript types, tests, and UI rendering.
