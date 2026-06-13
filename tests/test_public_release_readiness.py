from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def tracked_files(prefix: str) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", prefix],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def tracked_files_under(prefix: str) -> list[str]:
    normalized = prefix.rstrip("/")
    return [
        line
        for line in tracked_files(normalized)
        if line == normalized or line.startswith(normalized + "/")
    ]


def files_under(path: str) -> list[str]:
    root = ROOT / path
    if not root.exists():
        return []
    return sorted(
        str(candidate.relative_to(ROOT))
        for candidate in root.rglob("*")
        if candidate.is_file()
    )


def test_public_docs_exist() -> None:
    for path in [
        "docs/README.md",
        "docs/artifacts.md",
        "docs/concept-map.md",
        "docs/exercises.md",
        "docs/learning-path.md",
        "docs/quickstart.md",
        "docs/model-training-systems.md",
        "docs/runtime-proof.md",
        "docs/release-checklist.md",
        "docs/source-grounding.md",
    ]:
        assert (ROOT / path).is_file(), path


def test_public_readme_leads_with_three_layer_release_story() -> None:
    body = read("README.md")
    assert "Temporalis" in body
    assert "https://phi9t.github.io/temporalis/" in body
    assert "Tier 0" in body
    assert "Tier 1" in body
    assert "Tier 2" in body
    assert "make quickstart" in body
    assert "make runtime-proof" in body
    assert "64 A100" in body
    assert "FineWeb" in body
    assert "laptop" in body.lower()
    assert "docs index" in body
    assert "Learning Path" in body
    assert "Concept Map" in body
    assert "Exercises" in body
    assert "Reading Kilvin Artifacts" in body
    assert "Durable Model Training Systems" in body


def test_docs_index_is_the_learning_map() -> None:
    body = read("docs/README.md")
    for phrase in [
        "Temporalis Docs",
        "Quickstart",
        "Learning Path",
        "Concept Map",
        "Durable Model Training Systems",
        "Reading Kilvin Artifacts",
        "Exercises",
        "Source Grounding",
        "Runtime Proof",
        "Kilvin runbook",
        "Kilvin proof checklist",
        "Release checklist",
        "Temporal server, SDK Core, SDK Python, Temporal UI, and Kilvin",
        "intent, dependencies, quota, materialized launch specs, and monitoring",
    ]:
        assert phrase in body

    assert "docs index" in read("README.md")


def test_artifact_guide_explains_training_evidence_files() -> None:
    body = read("docs/artifacts.md")
    for phrase in [
        ".kilvin-artifacts/<run-id>/<attempt>/artifacts/pretrain/",
        "interpret_intent",
        "concretize_dependencies",
        "allocate_resources",
        "materialize_training_bundle",
        "submit_k8s_job",
        "monitor_training",
        "quota_decision.yaml",
        "env_vars.yaml",
        "logs.yaml",
        "image_digest",
        "lockfile_sha256",
        "job_manifest",
        "RUN_ID",
        "MODEL_NAME",
        "MAX_STEPS",
        "DATASET_MOUNT",
        "CHECKPOINT_URI",
        "checksum_sha256",
        "size_bytes",
        "heartbeating activity",
    ]:
        assert phrase in body

    assert "Reading Kilvin Artifacts" in read("README.md")
    assert "Reading Kilvin Artifacts" in read("docs/exercises.md")
    assert "Reading Kilvin Artifacts" in read("docs/concept-map.md")


def test_exercises_turn_hacks_and_runtime_into_learning_labs() -> None:
    body = read("docs/exercises.md")
    for phrase in [
        "make quickstart",
        "python3 hacks/001_source_map.py",
        "python3 hacks/002_lifecycle_manifest.py",
        "python3 hacks/003_task_queue_polling.py",
        "python3 hacks/004_history_replay.py",
        "python3 hacks/005_control_paths.py",
        "make kilvin-doctor",
        "make runtime-proof",
        "concretize_dependencies/out.yaml",
        "allocate_resources/quota_decision.yaml",
        "materialize_training_bundle/env_vars.yaml",
        "monitor_training/logs.yaml",
        "temporal workflow show",
        "temporal workflow signal",
        "activity side effects",
        "workflow decisions",
    ]:
        assert phrase in body

    assert "Exercises" in read("README.md")
    assert "Exercises" in read("docs/learning-path.md")


def test_concept_map_is_a_source_backed_short_reference() -> None:
    body = read("docs/concept-map.md")
    for phrase in [
        "Workflow",
        "Activity",
        "Task queue",
        "History",
        "Replay",
        "Signal",
        "Query",
        "Heartbeat",
        "Dependency concretization",
        "Quota and allocation",
        "Launch-spec materialization",
        "Kubernetes submission",
        "Monitoring",
        "Operator control",
        "kilvin-py/kilvin_py/workflows.py",
        "kilvin-py/kilvin_py/activities.py",
        "kilvin-py/worker.py",
        "interpret_training_intent",
        "concretize_dependencies",
        "allocate_resources",
        "materialize_training_bundle",
        "submit_k8s_job",
        "monitor_training",
    ]:
        assert phrase in body

    assert "Concept Map" in read("README.md")
    assert "Concept Map" in read("docs/learning-path.md")


def test_learning_path_maps_temporal_and_training_concepts_to_code() -> None:
    body = read("docs/learning-path.md")
    for phrase in [
        "train model X on FineWeb with 64 A100 GPUs",
        "Deep Dive / Lifecycle",
        "Deep Dive / Control Paths",
        "Deep Dive / Kilvin Internals",
        "workflow: the durable decision process",
        "activity: retryable side effects",
        "history: the durable source of truth",
        "replay: how Temporal reconstructs state",
        "CUDA/NCCL/Torch compatibility",
        "kilvin-py/kilvin_py/workflows.py",
        "kilvin-py/kilvin_py/activities.py",
        "concretize_dependencies",
        "interpret_training_intent",
        "monitor_training",
        "activity heartbeats",
        "signals recorded as history events",
        "make quickstart",
        "make runtime-proof",
    ]:
        assert phrase in body

    assert "Learning Path" in read("README.md")
    assert "Learning Path" in read("docs/quickstart.md")


def test_model_training_systems_doc_bridges_simple_kilvin_to_real_training() -> None:
    body = read("docs/model-training-systems.md")
    for phrase in [
        "Kilvin stays deliberately small",
        "production-shaped request",
        "multiple training phases",
        "huge token budgets",
        "CUDA, driver, NCCL, Torch",
        "scarce GPU quota",
        "activity heartbeats",
        "signals can pause, resume, cancel",
        "Deep Dive / Lifecycle",
        "Deep Dive / Kilvin Internals",
    ]:
        assert phrase in body

    quickstart = read("docs/quickstart.md")
    assert "Durable Model Training Systems" in quickstart
    assert "multi-phase training" in quickstart

    kilvin_readme = read("kilvin-py/README.md")
    assert "intentionally not a full foundation-model platform" in kilvin_readme
    assert "smallest real slice" in kilvin_readme


def test_public_docs_do_not_advertise_hidden_hackers_guide_ui() -> None:
    combined = "\n".join(
        [
            read("README.md"),
            read("explorer/README.md"),
            read("docs/quickstart.md"),
        ]
    )
    forbidden = [
        "rendered Hacker's Guide alongside the Deep Dive view",
        "Hacker's Guide mode",
        "Hacker's Guide tab",
        "Lifecycle, Control Paths, Kilvin Internals, and the Hacker's Guide",
        "links to its HACKERS_GUIDE.md section",
    ]
    for phrase in forbidden:
        assert phrase not in combined


def test_makefile_exposes_public_release_targets() -> None:
    makefile = read("Makefile")
    for target in [
        "quickstart:",
        "quickstart-check:",
        "verify-release:",
        "runtime-proof:",
    ]:
        assert re.search(rf"^{re.escape(target)}", makefile, re.MULTILINE), target


def test_agentic_release_artifacts_are_tracked_under_agents() -> None:
    assert tracked_files_under(".agent") == []
    assert files_under(".agent") == []
    tracked = set(tracked_files_under(".agents"))
    assert ".agents/checks/control_path_check.py" in tracked
    assert ".agents/notes/release-learning-session.md" in tracked


def load_quickstart_module():
    path = ROOT / "scripts" / "quickstart_check.py"
    spec = importlib.util.spec_from_file_location("quickstart_check", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quickstart_missing_ref_helper_reports_ids() -> None:
    quickstart = load_quickstart_module()
    assert quickstart.items_missing_refs(
        [
            {"id": "with-refs", "refs": [{"url": "https://example.test/#L1"}]},
            {"id": "without-refs", "refs": []},
            {"id": "missing-refs"},
        ]
    ) == ["without-refs", "missing-refs"]


def test_quickstart_required_generated_data_files_exist() -> None:
    quickstart = load_quickstart_module()
    missing = [
        path
        for path in quickstart.REQUIRED_DATA_FILES
        if not (ROOT / "explorer" / "public" / "data" / path).is_file()
    ]
    assert missing == []


def test_quickstart_checked_json_loader_reports_invalid_json(tmp_path) -> None:
    quickstart = load_quickstart_module()
    quickstart.DATA = tmp_path
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")

    failures: list[str] = []

    assert quickstart.load_json_checked("bad.json", failures) is None
    assert len(failures) == 1
    assert failures[0].startswith("generated data is invalid JSON: bad.json:")


def test_quickstart_control_path_index_reports_malformed_entries(tmp_path) -> None:
    quickstart = load_quickstart_module()
    quickstart.DATA = tmp_path
    (tmp_path / "control-paths").mkdir()
    (tmp_path / "control-paths" / "index.json").write_text(
        '[{"manifest": 12, "slug": "bad-manifest"}, {"manifest": "missing.json"}]',
        encoding="utf-8",
    )

    failures: list[str] = []

    quickstart.check_control_paths(failures)
    assert "control-path entry has non-string manifest: bad-manifest" in failures
    assert "control-path entry missing string slug" in failures
