from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "explorer" / "public" / "data"
SCRIPTS = ROOT / "explorer" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_lifecycle_data import guide_link, read_hack_metadata, validate_hack_guide_anchors


def run_generator() -> None:
    subprocess.run(
        [sys.executable, "explorer/scripts/build_lifecycle_data.py", "--repo-root", "."],
        cwd=ROOT,
        check=True,
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def lock_heads() -> dict[str, str]:
    lock = load_json(ROOT / ".monorepo" / "current.lock.json")
    return {repo["id"]: repo["head"] for repo in lock["repos"]}


def ref_line(ref: dict) -> str:
    if ref["repo"] == "kilvin":
        base = ROOT
    else:
        base = ROOT / ref["repo"]
        if not base.exists():
            main_checkout = ROOT.parents[1] if ROOT.parent.name == ".worktrees" else ROOT
            base = main_checkout / ref["repo"]
    return (base / ref["path"]).read_text(encoding="utf-8").splitlines()[ref["line"] - 1]


def find_ref(refs: list[dict], repo: str, path: str, label: str) -> dict:
    for ref in refs:
        if ref["repo"] == repo and ref["path"] == path and ref["label"] == label:
            return ref
    raise AssertionError(f"missing ref {repo}:{path}:{label}")


def explicit_guide_anchors() -> set[str]:
    guide = (ROOT / "HACKERS_GUIDE.md").read_text(encoding="utf-8")
    return set(re.findall(r'<a\s+id="([^"]+)"></a>', guide))


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


def test_lifecycle_calls_are_generated_and_reference_manifest_parts() -> None:
    run_generator()
    manifest = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    phase_ids = {phase["id"] for phase in manifest["phases"]}
    node_ids = {node["id"] for node in manifest["nodes"]}
    edges = {edge["id"]: edge for edge in manifest["edges"]}

    calls = manifest["calls"]
    assert calls
    assert {call["phase_id"] for call in calls} == phase_ids
    calls_by_id = {call["id"]: call for call in calls}
    required_call_ids = {
        "call-core-poll-matching",
        "call-matching-workflow-task",
        "call-core-poll-activity-task",
        "call-matching-activity-task",
        "call-core-activity-task",
    }
    assert required_call_ids <= calls_by_id.keys()
    assert calls_by_id["call-core-poll-matching"]["kind"] == "poll"
    assert calls_by_id["call-matching-workflow-task"]["kind"] == "response"
    assert calls_by_id["call-core-poll-activity-task"]["kind"] == "poll"
    assert calls_by_id["call-matching-activity-task"]["kind"] == "response"
    assert calls_by_id["call-matching-activity-task"]["seq"] < calls_by_id["call-core-activity-task"]["seq"]

    seqs = [call["seq"] for call in calls]
    assert len(seqs) == len(set(seqs))
    assert sorted(seqs) == list(range(1, len(calls) + 1))

    for call in calls:
        assert call["phase_id"] in phase_ids
        assert call["from"] in node_ids
        assert call["to"] in node_ids
        assert call["edge_id"] in edges
        assert isinstance(call["refs"], list)
        for ref in call["refs"]:
            assert ref["repo"]
            assert ref["path"]
            assert isinstance(ref["line"], int) and ref["line"] > 0

        edge = edges[call["edge_id"]]
        if call["kind"] == "response":
            assert (edge["from"], edge["to"]) == (call["from"], call["to"]) or (edge["from"], edge["to"]) == (
                call["to"],
                call["from"],
            )
        else:
            assert (edge["from"], edge["to"]) == (call["from"], call["to"])


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

    assert "await client.execute_workflow(" in ref_line(start_ref)
    assert "async def _handle_activation(" in ref_line(activation_ref)
    assert "func" in ref_line(frontend_ref)
    assert "StartWorkflowExecution(" in ref_line(frontend_ref)


def test_source_ref_urls_follow_pinning_policy() -> None:
    run_generator()
    manifest = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    refs = [ref for node in manifest["nodes"] for ref in node["refs"]]
    heads = lock_heads()

    for ref in refs:
        if ref["repo"] == "kilvin":
            assert ref["url"].startswith("https://github.com/phi9t/temporalis/blob/phi9t-mainline/")
            assert ref.get("ref") == "phi9t-mainline"
        else:
            assert heads[ref["repo"]] in ref["url"]


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


def test_public_guide_copy_matches_root_guide() -> None:
    run_generator()
    root_guide = (ROOT / "HACKERS_GUIDE.md").read_text(encoding="utf-8")
    assert (ROOT / "explorer" / "public" / "HACKERS_GUIDE.md").read_text(encoding="utf-8") == root_guide
    assert (OUT / "guide.md").read_text(encoding="utf-8") == root_guide


def test_generated_guide_anchors_are_linkable_from_guide() -> None:
    run_generator()
    linkable_anchors = explicit_guide_anchors()
    guide = json.loads((OUT / "guide" / "index.json").read_text(encoding="utf-8"))
    lifecycle = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    control_index = json.loads((OUT / "control-paths" / "index.json").read_text(encoding="utf-8"))
    control_scenarios = [load_json(OUT / entry["manifest"]) for entry in control_index]

    generated_anchors = {entry["anchor"] for entry in guide["sections"]}
    generated_anchors |= {entry["guide_anchor"] for entry in guide["hacks"]}
    generated_anchors |= {phase["guide_anchor"] for phase in lifecycle["phases"]}
    generated_anchors |= {scenario["guide_anchor"] for scenario in control_scenarios}

    assert generated_anchors <= linkable_anchors


def test_hack_metadata_includes_supported_guide_anchors() -> None:
    run_generator()
    guide = json.loads((OUT / "guide" / "index.json").read_text(encoding="utf-8"))
    hacks = {entry["script"]: entry for entry in guide["hacks"]}

    lifecycle = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    control_index = json.loads((OUT / "control-paths" / "index.json").read_text(encoding="utf-8"))
    control_scenarios = [load_json(OUT / entry["manifest"]) for entry in control_index]

    for item in [*lifecycle["phases"], *control_scenarios]:
        hack = hacks[item["hack_script"]]
        assert item["guide_anchor"] in hack["guide_anchors"]


def test_guide_link_rejects_anchor_not_supported_by_hack(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "hacks").mkdir()
    script = repo / "hacks" / "001_demo.py"
    script.write_text(
        'GUIDE_ANCHOR = "primary"\nSUMMARY = "Demo hack."\n',
        encoding="utf-8",
    )
    hacks = read_hack_metadata(repo)

    with pytest.raises(ValueError, match="does not support guide anchor"):
        guide_link(repo, {"primary": "Primary", "secondary": "Secondary"}, hacks, "secondary", "hacks/001_demo.py")


def test_hack_metadata_rejects_supported_anchor_missing_from_guide(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "hacks").mkdir()
    (repo / "hacks" / "001_demo.py").write_text(
        'GUIDE_ANCHOR = "primary"\nGUIDE_ANCHORS = ("primary", "typo")\nSUMMARY = "Demo hack."\n',
        encoding="utf-8",
    )
    hacks = read_hack_metadata(repo)

    with pytest.raises(ValueError, match="unsupported guide anchor 'typo'"):
        validate_hack_guide_anchors({"primary": "Primary"}, hacks)


def test_read_hack_metadata_requires_valid_numbered_metadata(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "hacks").mkdir()

    (repo / "hacks" / "001_missing_summary.py").write_text(
        'GUIDE_ANCHOR = "primary"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing SUMMARY"):
        read_hack_metadata(repo)

    (repo / "hacks" / "001_missing_summary.py").write_text(
        'GUIDE_ANCHOR = "primary"\nSUMMARY = "Demo hack."\n',
        encoding="utf-8",
    )
    (repo / "hacks" / "002_bad_anchor.py").write_text(
        'GUIDE_ANCHOR = ["primary"]\nSUMMARY = "Demo hack."\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="GUIDE_ANCHOR must be a string"):
        read_hack_metadata(repo)

    (repo / "hacks" / "002_bad_anchor.py").write_text(
        'GUIDE_ANCHOR = "primary"\nGUIDE_ANCHORS = ("primary", 2)\nSUMMARY = "Demo hack."\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="GUIDE_ANCHORS must contain only strings"):
        read_hack_metadata(repo)


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
