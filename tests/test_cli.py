from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from monoctl.cli import main

from tests.helpers import init_git_repo


def test_doctor_returns_failure_for_dirty_repo(
    tmp_path: Path, capsys
) -> None:
    repo_path = tmp_path / "sdk-go"
    init_git_repo(repo_path)
    (repo_path / "README.md").write_text("# changed\n", encoding="utf-8")

    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: sdk-go
    path: {repo_path}
    role: sdk
    upstream_remote: origin
    expected_default_branch: main
    criticality: high
""".strip()
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["doctor", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "dirty worktree" in captured.out.lower()


def test_doctor_returns_failure_for_missing_repo_path(
    tmp_path: Path, capsys
) -> None:
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        """
repos:
  - id: temporal
    path: missing-temporal
    role: engine
    upstream_remote: origin
    expected_default_branch: main
    criticality: high
""".strip()
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["doctor", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "missing path" in captured.out.lower()


def test_snapshot_writes_lockfile_and_markdown_report(
    tmp_path: Path, capsys
) -> None:
    repo_path = tmp_path / "cli"
    init_git_repo(repo_path)
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: cli
    path: {repo_path}
    role: cli
    upstream_remote: origin
    expected_default_branch: main
    criticality: high
""".strip()
        + "\n",
        encoding="utf-8",
    )
    lockfile = tmp_path / "current.lock.json"
    report_dir = tmp_path / "reports"

    exit_code = main(
        [
            "snapshot",
            "--manifest",
            str(manifest),
            "--lockfile",
            str(lockfile),
            "--report-dir",
            str(report_dir),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert lockfile.exists()
    reports = list(report_dir.glob("*.md"))
    assert len(reports) == 1
    assert "cli" in lockfile.read_text(encoding="utf-8")
    assert "Monorepo Snapshot" in reports[0].read_text(encoding="utf-8")
    assert "Wrote" in captured.out


def test_module_entrypoint_executes_status_command(tmp_path: Path) -> None:
    repo_path = tmp_path / "temporal"
    init_git_repo(repo_path)
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: temporal
    path: {repo_path}
    role: engine
    upstream_remote: origin
    expected_default_branch: main
    criticality: high
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "monoctl.cli",
            "status",
            "--manifest",
            str(manifest),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "temporal: branch=main" in result.stdout


def test_status_includes_describe_and_remote_summary(
    tmp_path: Path, capsys
) -> None:
    repo_path = tmp_path / "sdk-core"
    init_git_repo(repo_path, branch="master")
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: sdk-core
    path: {repo_path}
    role: shared runtime
    upstream_remote: origin
    expected_default_branch: master
    criticality: critical
""".strip()
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["status", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "describe=" in captured.out
    assert "origin=git@github.com:example/sdk-core.git" in captured.out


def test_init_clones_missing_repos_from_manifest(tmp_path: Path, monkeypatch, capsys) -> None:
    repo_path = tmp_path / "temporal"
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: temporal
    path: {repo_path}
    role: engine
    upstream_remote: origin
    expected_remote_url: git@github.com:temporalio/temporal.git
    expected_default_branch: main
    criticality: high
""".strip()
        + "\n",
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path) -> None:
        commands.append(command)

    monkeypatch.setattr("monoctl.cli._run_git_command", fake_run, raising=False)

    exit_code = main(["init", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert commands == [
        [
            "git",
            "clone",
            "--branch",
            "main",
            "git@github.com:temporalio/temporal.git",
            str(repo_path),
        ]
    ]
    assert "Cloned temporal" in captured.out


def test_init_pulls_clean_existing_repos(tmp_path: Path, monkeypatch, capsys) -> None:
    repo_path = tmp_path / "sdk-python"
    init_git_repo(repo_path, branch="main")
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: sdk-python
    path: {repo_path}
    role: sdk
    upstream_remote: origin
    expected_remote_url: git@github.com:example/sdk-python.git
    expected_default_branch: main
    criticality: critical
""".strip()
        + "\n",
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path) -> None:
        commands.append(command)

    monkeypatch.setattr("monoctl.cli._run_git_command", fake_run, raising=False)

    exit_code = main(["init", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert commands == [["git", "pull", "--ff-only", "origin", "main"]]
    assert "Pulled sdk-python" in captured.out


def test_init_fails_without_mutating_dirty_repo(tmp_path: Path, monkeypatch, capsys) -> None:
    repo_path = tmp_path / "sdk-go"
    init_git_repo(repo_path, branch="main")
    (repo_path / "README.md").write_text("# changed\n", encoding="utf-8")
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: sdk-go
    path: {repo_path}
    role: sdk
    upstream_remote: origin
    expected_remote_url: git@github.com:example/sdk-go.git
    expected_default_branch: main
    criticality: critical
""".strip()
        + "\n",
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path) -> None:
        commands.append(command)

    monkeypatch.setattr("monoctl.cli._run_git_command", fake_run, raising=False)

    exit_code = main(["init", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert commands == []
    assert "dirty worktree" in captured.out.lower()


def test_init_fails_without_mutating_wrong_branch_repo(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo_path = tmp_path / "sdk-core"
    init_git_repo(repo_path, branch="feature")
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: sdk-core
    path: {repo_path}
    role: shared runtime
    upstream_remote: origin
    expected_remote_url: git@github.com:example/sdk-core.git
    expected_default_branch: main
    criticality: critical
""".strip()
        + "\n",
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path) -> None:
        commands.append(command)

    monkeypatch.setattr("monoctl.cli._run_git_command", fake_run, raising=False)

    exit_code = main(["init", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert commands == []
    assert "branch mismatch" in captured.out.lower()


def test_init_reports_git_command_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    repo_path = tmp_path / "temporal"
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        f"""
repos:
  - id: temporal
    path: {repo_path}
    role: engine
    upstream_remote: origin
    expected_remote_url: git@github.com:temporalio/temporal.git
    expected_default_branch: main
    criticality: high
""".strip()
        + "\n",
        encoding="utf-8",
    )

    def fake_run(command: list[str], cwd: Path) -> None:
        raise subprocess.CalledProcessError(returncode=128, cmd=command)

    monkeypatch.setattr("monoctl.cli._run_git_command", fake_run, raising=False)

    exit_code = main(["init", "--manifest", str(manifest)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAIL: temporal: git command failed with exit 128" in captured.out
