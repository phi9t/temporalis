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


def test_doctor_fails_when_k3s_node_has_disk_pressure(monkeypatch, tmp_path: Path) -> None:
    doctor = load_script("kilvin_doctor.py")
    kubeconfig = tmp_path / "kubeconfig.yaml"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")

    monkeypatch.setattr(doctor, "command_exists", lambda name: name == "kubectl")
    monkeypatch.setattr(doctor, "KUBECONFIG", kubeconfig)

    def fake_run_command(cmd: list[str], *, timeout: int = 30):
        assert "describe" in cmd
        return doctor.subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Conditions:\n  DiskPressure True KubeletHasDiskPressure kubelet has disk pressure\n",
            stderr="",
        )

    monkeypatch.setattr(doctor, "run_command", fake_run_command)

    result = doctor.check_k3s_disk_pressure()

    assert result.status == "FAIL"
    assert result.required is True
    assert "disk-pressure" in result.detail
    assert "docker system df" in result.detail


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


def test_trainer_dockerignore_excludes_local_virtualenv_and_caches() -> None:
    dockerignore = (REPO_ROOT / "kilvin-py" / "trainer" / ".dockerignore").read_text(
        encoding="utf-8"
    )

    for pattern in [
        ".venv/",
        "__pycache__/",
        "*.pyc",
        "out/",
    ]:
        assert pattern in dockerignore


def test_infra_up_bootstraps_homebrew_tool_path() -> None:
    up_script = (REPO_ROOT / "kilvin-py" / "infra" / "up.sh").read_text(encoding="utf-8")

    assert "export PATH=\"/opt/homebrew/bin:$PATH\"" in up_script


def test_infra_up_builds_allocator_with_host_resolved_package_domains() -> None:
    up_script = (REPO_ROOT / "kilvin-py" / "infra" / "up.sh").read_text(encoding="utf-8")

    assert "files.pythonhosted.org" in up_script
    assert "download.pytorch.org" in up_script
    assert "--add-host" in up_script
    assert "docker build" in up_script
    assert "docker compose up -d --no-build" in up_script


def test_root_makefile_exposes_kilvin_runtime_commands() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    for target in [
        "kilvin-doctor:",
        "kilvin-up:",
        "kilvin-down:",
        "kilvin-clean:",
        "kilvin-real-smoke:",
    ]:
        assert target in makefile

    assert "$(MAKE) kilvin-up" in makefile
    assert "python3 scripts/kilvin_clean.py" in makefile


def test_mise_exposes_root_kilvin_tasks() -> None:
    mise = (REPO_ROOT / ".mise.toml").read_text(encoding="utf-8")

    for task in [
        '[tasks."kilvin:doctor"]',
        '[tasks."kilvin:up"]',
        '[tasks."kilvin:down"]',
        '[tasks."kilvin:clean"]',
        '[tasks."kilvin:smoke"]',
    ]:
        assert task in mise

    assert "make kilvin-up" in mise
    assert "make kilvin-clean" in mise


def test_kilvin_clean_keeps_active_and_recent_trainer_images() -> None:
    clean = load_script("kilvin_clean.py")

    images = [
        clean.DockerImage("localhost:5001/kilvin-trainer", "run-active", "img-active"),
        clean.DockerImage("localhost:5001/kilvin-trainer", "run-new", "img-new"),
        clean.DockerImage("localhost:5001/kilvin-trainer", "run-old", "img-old"),
        clean.DockerImage("ubuntu", "24.04", "img-ubuntu"),
    ]

    selected = clean.select_trainer_images_to_remove(
        images,
        active_run_ids={"run-active"},
        keep_recent=1,
    )

    assert selected == [images[2]]
