#!/usr/bin/env python3
"""Preflight the local environment for the real Kilvin runtime."""

from __future__ import annotations

import argparse
import dataclasses
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "kilvin-py" / "infra" / "docker-compose.yml"
KUBECONFIG = REPO_ROOT / "kilvin-py" / "infra" / ".kubeconfig" / "kubeconfig.yaml"
EXTRA_TOOL_DIRS = (REPO_ROOT / ".venv" / "bin", Path("/opt/homebrew/bin"))


@dataclasses.dataclass(frozen=True)
class CheckResult:
    status: str
    name: str
    detail: str
    required: bool = True

    @property
    def failed(self) -> bool:
        return self.status == "FAIL" and self.required


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


def run_command(cmd: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(resolve_command(cmd), text=True, capture_output=True, timeout=timeout, check=False)


def command_exists(name: str) -> bool:
    return find_command(name) is not None


def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def result_exit_code(results: list[CheckResult]) -> int:
    return 1 if any(result.failed for result in results) else 0


def check_tool(name: str, *, required: bool = True) -> CheckResult:
    if command_exists(name):
        return CheckResult("PASS", f"tool:{name}", "found", required)
    status = "FAIL" if required else "WARN"
    return CheckResult(status, f"tool:{name}", "not found on PATH", required)


def check_docker_context() -> CheckResult:
    result = run_command(["docker", "context", "show"])
    if result.returncode != 0:
        return CheckResult("FAIL", "docker context", result.stderr.strip() or "docker context failed")
    context = result.stdout.strip()
    if context != "colima":
        return CheckResult("WARN", "docker context", f"active context is {context!r}, expected 'colima'", False)
    return CheckResult("PASS", "docker context", context)


def check_docker_daemon() -> CheckResult:
    result = run_command(
        ["docker", "info", "--format", "{{.OperatingSystem}} | {{.Architecture}}"],
        timeout=20,
    )
    if result.returncode != 0:
        return CheckResult("FAIL", "docker daemon", result.stderr.strip() or "docker info failed")
    return CheckResult("PASS", "docker daemon", result.stdout.strip())


def check_amd64_container() -> CheckResult:
    result = run_command(
        ["docker", "run", "--rm", "--platform", "linux/amd64", "alpine:3.20", "uname", "-m"],
        timeout=60,
    )
    if result.returncode != 0:
        return CheckResult("FAIL", "linux/amd64 container", result.stderr.strip() or "container run failed")
    arch = result.stdout.strip()
    if arch != "x86_64":
        return CheckResult("FAIL", "linux/amd64 container", f"reported {arch!r}, expected x86_64")
    return CheckResult("PASS", "linux/amd64 container", arch)


def check_compose_status() -> CheckResult:
    if not COMPOSE_FILE.exists():
        return CheckResult("FAIL", "compose file", f"missing {COMPOSE_FILE}")
    result = run_command(["docker", "compose", "-f", str(COMPOSE_FILE), "ps"], timeout=30)
    if result.returncode != 0:
        return CheckResult("WARN", "compose services", result.stderr.strip() or "compose stack not reachable", False)
    if "kilvin-infra" not in result.stdout:
        return CheckResult("WARN", "compose services", "stack appears down; run kilvin-py/infra/up.sh", False)
    return CheckResult("PASS", "compose services", "stack visible")


def check_kubectl_namespace() -> CheckResult:
    if not KUBECONFIG.exists():
        return CheckResult("WARN", "k3s kubeconfig", f"missing {KUBECONFIG}; run kilvin-py/infra/up.sh", False)
    if not command_exists("kubectl"):
        return CheckResult("WARN", "kubectl namespace", "kubectl not found; skipping namespace check", False)
    result = run_command(
        [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "get",
            "namespace",
            "kilvin-training",
        ],
        timeout=20,
    )
    if result.returncode != 0:
        return CheckResult("WARN", "kubectl namespace", result.stderr.strip() or "namespace check failed", False)
    return CheckResult("PASS", "kubectl namespace", "kilvin-training exists")


def collect_checks() -> list[CheckResult]:
    results = [
        check_tool("docker"),
        check_tool("uv"),
        check_tool("python3"),
        check_tool("curl"),
        check_tool("kubectl", required=False),
        check_tool("temporal", required=False),
    ]
    if command_exists("docker"):
        results.extend([check_docker_context(), check_docker_daemon(), check_amd64_container()])
    results.extend(
        [
            check_compose_status(),
            CheckResult(
                "PASS" if http_ok("http://localhost:7070/healthz") else "WARN",
                "allocator health",
                "http://localhost:7070/healthz" if http_ok("http://localhost:7070/healthz") else "not reachable; run kilvin-py/infra/up.sh",
                False,
            ),
            CheckResult(
                "PASS" if tcp_open("localhost", 7233) else "WARN",
                "Temporal port",
                "localhost:7233 open" if tcp_open("localhost", 7233) else "localhost:7233 closed; run kilvin-py/infra/up.sh",
                False,
            ),
            CheckResult(
                "PASS" if tcp_open("localhost", 5001) else "WARN",
                "registry port",
                "localhost:5001 open" if tcp_open("localhost", 5001) else "localhost:5001 closed; run kilvin-py/infra/up.sh",
                False,
            ),
            check_kubectl_namespace(),
        ]
    )
    return results


def print_results(results: list[CheckResult]) -> None:
    for result in results:
        print(f"{result.status:<4} {result.name:<24} {result.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    results = collect_checks()
    print_results(results)
    exit_code = result_exit_code(results)
    if exit_code:
        print("\nFix FAIL rows before running the live Kilvin smoke proof.")
    else:
        print("\nDoctor complete. WARN rows are optional or indicate infra is not currently running.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
