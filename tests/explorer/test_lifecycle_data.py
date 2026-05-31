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


def local_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def ref_line(ref: dict) -> str:
    if ref["repo"] == "kilvin":
        base = ROOT
    else:
        base = ROOT / ref["repo"]
    return (base / ref["path"]).read_text(encoding="utf-8").splitlines()[ref["line"] - 1]


def find_ref(refs: list[dict], repo: str, path: str, label: str) -> dict:
    for ref in refs:
        if ref["repo"] == repo and ref["path"] == path and ref["label"] == label:
            return ref
    raise AssertionError(f"missing ref {repo}:{path}:{label}")


def test_lifecycle_manifest_is_schema_consistent() -> None:
    run_generator()
    manifest = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    node_ids = {node["id"] for node in manifest["nodes"]}
    edge_ids = {(edge["from"], edge["to"]) for edge in manifest["edges"]}

    assert {
        "kilvin-client",
        "python-worker",
        "bridge-worker",
        "core-worker",
        "frontend-service",
        "history-service",
        "matching-service",
    } <= node_ids
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


def test_important_source_refs_resolve_to_intended_lines() -> None:
    run_generator()
    manifest = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    refs = [ref for node in manifest["nodes"] for ref in node["refs"]]

    start_ref = find_ref(refs, "kilvin", "kilvin-py/start_workflow.py", "start_workflow.py")
    activation_ref = find_ref(refs, "sdk-python", "temporalio/worker/_workflow.py", "_handle_activation")
    frontend_ref = find_ref(refs, "temporal", "service/frontend/workflow_handler.go", "StartWorkflowExecution")
    kilvin_worker_ref = find_ref(refs, "kilvin", "kilvin-py/worker.py", "kilvin worker")

    assert "await client.execute_workflow(" in ref_line(start_ref)
    assert "async def _handle_activation(" in ref_line(activation_ref)
    assert "func" in ref_line(frontend_ref)
    assert "StartWorkflowExecution(" in ref_line(frontend_ref)
    assert local_head() in start_ref["url"]
    assert local_head() in kilvin_worker_ref["url"]
    assert "phi9t-mainline" not in start_ref["url"]


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
