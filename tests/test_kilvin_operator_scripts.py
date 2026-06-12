from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def test_pages_missing_expected_strings() -> None:
    pages = load_script("kilvin_pages_check.py")

    assert pages.missing_expected_strings("laptop scale uv lock --check local allocator k3s") == []
    assert pages.missing_expected_strings("laptop scale k3s") == [
        "uv lock --check",
        "local allocator",
    ]


def test_doctor_exit_code_only_fails_required_failures() -> None:
    doctor = load_script("kilvin_doctor.py")

    results = [
        doctor.CheckResult("PASS", "docker", "ok"),
        doctor.CheckResult("WARN", "allocator", "not running", required=False),
    ]
    assert doctor.result_exit_code(results) == 0

    results.append(doctor.CheckResult("FAIL", "docker daemon", "unreachable"))
    assert doctor.result_exit_code(results) == 1


def test_smoke_extracts_completed_run_id() -> None:
    smoke = load_script("kilvin_real_smoke.py")

    assert smoke.extract_completed_run_id("Result: KILVIN_TRAINING_COMPLETED:run-123abc\n") == "run-123abc"
    assert smoke.extract_completed_run_id("workflow failed") is None


def test_smoke_artifact_proof_detection(tmp_path: Path) -> None:
    smoke = load_script("kilvin_real_smoke.py")
    stage_dir = tmp_path / "run-1" / "1" / "artifacts" / "pretrain"
    (stage_dir / "concretize_dependencies").mkdir(parents=True)
    (stage_dir / "allocate_resources").mkdir()
    (stage_dir / "materialize_training_bundle").mkdir()
    (stage_dir / "monitor_training").mkdir()
    (stage_dir / "concretize_dependencies" / "out.yaml").write_text(
        "image_digest: sha256:abc\n", encoding="utf-8"
    )
    (stage_dir / "allocate_resources" / "quota_decision.yaml").write_text(
        "cluster: local-k3s\n", encoding="utf-8"
    )
    (stage_dir / "materialize_training_bundle" / "env_vars.yaml").write_text(
        "RUN_ID: run-1\n", encoding="utf-8"
    )
    (stage_dir / "monitor_training" / "logs.yaml").write_text(
        "TRAINING_DONE run_id=run-1\n", encoding="utf-8"
    )

    assert smoke.find_stage_artifact_dir("run-1", tmp_path) == stage_dir
    assert smoke.missing_artifact_proofs(stage_dir) == []

    (stage_dir / "monitor_training" / "logs.yaml").write_text("step=1\n", encoding="utf-8")
    assert "monitor_training/logs.yaml lacks 'TRAINING_DONE'" in smoke.missing_artifact_proofs(
        stage_dir
    )
