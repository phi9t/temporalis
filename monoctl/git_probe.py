from __future__ import annotations

import subprocess
from pathlib import Path

from monoctl.models import RepoState


def _run_git(repo_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=check,
    )


def is_git_repo(repo_path: Path) -> bool:
    if not repo_path.exists():
        return False
    result = _run_git(repo_path, "rev-parse", "--git-dir", check=False)
    return result.returncode == 0


def _branch(repo_path: Path) -> str | None:
    result = _run_git(repo_path, "symbolic-ref", "--short", "HEAD", check=False)
    return result.stdout.strip() or None


def _describe(repo_path: Path) -> str | None:
    result = _run_git(repo_path, "describe", "--tags", "--always", "--dirty", check=False)
    return result.stdout.strip() or None


def _dirty_summary(repo_path: Path) -> list[str]:
    result = _run_git(repo_path, "status", "--short", check=False)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _remotes(repo_path: Path) -> dict[str, str]:
    result = _run_git(repo_path, "remote", "-v", check=False)
    remotes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "(fetch)":
            remotes[parts[0]] = parts[1]
    return remotes


def inspect_repo(repo_path: Path, repo_id: str | None = None, display_path: str | None = None) -> RepoState:
    head = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()
    dirty_summary = _dirty_summary(repo_path)
    return RepoState(
        id=repo_id or repo_path.name,
        path=display_path or str(repo_path),
        branch=_branch(repo_path),
        head=head,
        describe=_describe(repo_path),
        is_dirty=bool(dirty_summary),
        dirty_summary=dirty_summary,
        remotes=_remotes(repo_path),
    )
