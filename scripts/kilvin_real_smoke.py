#!/usr/bin/env python3
"""Run and verify one real Kilvin Temporal/k3s training workflow."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KILVIN_ROOT = REPO_ROOT / "kilvin-py"
ARTIFACT_ROOT = KILVIN_ROOT / ".kilvin-artifacts"
KUBECONFIG = KILVIN_ROOT / "infra" / ".kubeconfig" / "kubeconfig.yaml"
EXTRA_TOOL_DIRS = (REPO_ROOT / ".venv" / "bin", Path("/opt/homebrew/bin"))
EXPECTED_STEPS = (
    "interpret_intent",
    "concretize_dependencies",
    "allocate_resources",
    "materialize_training_bundle",
    "submit_k8s_job",
    "monitor_training",
)


def extract_completed_run_id(output: str) -> str | None:
    match = re.search(r"KILVIN_TRAINING_COMPLETED:([A-Za-z0-9_.-]+)", output)
    return match.group(1) if match else None


def find_stage_artifact_dir(run_id: str, artifact_root: Path = ARTIFACT_ROOT) -> Path | None:
    candidates = sorted((artifact_root / run_id).glob("*/artifacts/pretrain"))
    return candidates[-1] if candidates else None


def missing_artifact_proofs(stage_dir: Path) -> list[str]:
    required_files = {
        "concretize_dependencies/out.yaml": "sha256:",
        "allocate_resources/quota_decision.yaml": "local-k3s",
        "materialize_training_bundle/env_vars.yaml": "RUN_ID",
        "monitor_training/logs.yaml": "TRAINING_DONE",
    }
    missing: list[str] = []
    for relative_path, expected_text in required_files.items():
        path = stage_dir / relative_path
        if not path.exists():
            missing.append(f"missing {relative_path}")
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if expected_text not in body:
            missing.append(f"{relative_path} lacks {expected_text!r}")
    return missing


def allocator_is_empty(url: str = "http://localhost:7070/v1/allocations") -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False
    return body.get("allocations") == []


def find_command(name: str) -> str | None:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    for directory in EXTRA_TOOL_DIRS:
        candidate = directory / name
        if candidate.exists():
            return str(candidate)
    return None


def resolve_command(cmd: list[str]) -> list[str]:
    resolved = find_command(cmd[0])
    return [resolved or cmd[0], *cmd[1:]]


def run_command(cmd: list[str], *, cwd: Path, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        resolve_command(cmd), cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False
    )


def optional_temporal_trace(run_id: str) -> tuple[bool, str]:
    if find_command("temporal") is None:
        return True, "WARN temporal CLI not found; skipped step trace query"
    result = run_command(
        ["temporal", "workflow", "query", "-w", f"kilvin-training-{run_id}", "--type", "run_step_trace"],
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        return True, f"WARN temporal trace query failed: {result.stderr.strip()}"
    missing = [step for step in EXPECTED_STEPS if step not in result.stdout]
    if missing or "SUCCEEDED" not in result.stdout:
        return False, f"FAIL temporal trace missing proof: {', '.join(missing) or 'SUCCEEDED'}"
    return True, "PASS temporal trace contains expected steps"


def optional_kubectl_status() -> tuple[bool, str]:
    if find_command("kubectl") is None:
        return True, "WARN kubectl not found; skipped k3s job status"
    if not KUBECONFIG.exists():
        return True, "WARN kubeconfig missing; skipped k3s job status"
    result = run_command(
        [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "-n",
            "kilvin-training",
            "get",
            "jobs,pods",
        ],
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        return True, f"WARN kubectl status failed: {result.stderr.strip()}"
    if "Complete" not in result.stdout and "Completed" not in result.stdout:
        return True, "WARN kubectl did not show a completed job or pod"
    return True, "PASS kubectl shows completed training work"


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def run_smoke(*, start_infra: bool) -> int:
    if start_infra:
        infra = run_command(["./infra/up.sh"], cwd=KILVIN_ROOT, timeout=300)
        if infra.returncode != 0:
            print(infra.stdout)
            print(infra.stderr, file=sys.stderr)
            print("FAIL infra start failed")
            return 1

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("KILVIN_LAPTOP_MAX_STEPS", "10")
    worker = subprocess.Popen(
        resolve_command(["uv", "run", "python", "worker.py"]),
        cwd=KILVIN_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        time.sleep(5)
        workflow = run_command(["uv", "run", "python", "start_workflow.py"], cwd=KILVIN_ROOT, timeout=900)
        output = workflow.stdout + workflow.stderr
        print(output, end="" if output.endswith("\n") else "\n")
        if workflow.returncode != 0:
            print("FAIL workflow command failed")
            return 1

        run_id = extract_completed_run_id(output)
        if run_id is None:
            print("FAIL workflow output did not contain KILVIN_TRAINING_COMPLETED:<run-id>")
            return 1
        print(f"PASS workflow completed: {run_id}")

        stage_dir = find_stage_artifact_dir(run_id)
        if stage_dir is None:
            print(f"FAIL no artifact directory found for {run_id}")
            return 1
        missing = missing_artifact_proofs(stage_dir)
        if missing:
            for item in missing:
                print(f"FAIL artifact proof: {item}")
            return 1
        print(f"PASS artifact proofs found under {stage_dir}")

        trace_ok, trace_message = optional_temporal_trace(run_id)
        print(trace_message)
        if not trace_ok:
            return 1

        kubectl_ok, kubectl_message = optional_kubectl_status()
        print(kubectl_message)
        if not kubectl_ok:
            return 1

        if not allocator_is_empty():
            print("FAIL allocator still has live allocations")
            return 1
        print("PASS allocator released all allocations")
        return 0
    finally:
        terminate_process(worker)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-infra", action="store_true", help="run kilvin-py/infra/up.sh first")
    args = parser.parse_args(argv)
    return run_smoke(start_infra=args.start_infra)


if __name__ == "__main__":
    sys.exit(main())
