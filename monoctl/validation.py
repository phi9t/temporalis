from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from monoctl.models import Manifest, RepoState
from monoctl.workspace import resolve_repo_path

ValidationMode = Literal["doctor", "init"]


@dataclass(slots=True)
class ValidationResult:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_workspace(
    manifest_path: Path,
    manifest: Manifest,
    states: list[RepoState],
    *,
    mode: ValidationMode,
) -> ValidationResult:
    result = ValidationResult()
    for repo, state in zip(manifest.repos, states, strict=True):
        repo_path = resolve_repo_path(manifest_path, repo)
        if not repo_path.exists():
            if mode == "init":
                if not repo.expected_remote_url:
                    result.failures.append(
                        f"{repo.id}: missing expected_remote_url for clone"
                    )
                continue
            result.failures.append(f"{repo.id}: missing path {repo.path}")
            continue

        if state.head == "missing":
            result.failures.append(f"{repo.id}: path is not a git repo ({repo.path})")
            continue

        remote_url = state.remotes.get(repo.upstream_remote)
        if remote_url is None:
            result.failures.append(
                f"{repo.id}: missing upstream remote {repo.upstream_remote}"
            )
        elif repo.expected_remote_url and remote_url != repo.expected_remote_url:
            result.failures.append(
                f"{repo.id}: remote {repo.upstream_remote} URL mismatch "
                f"({remote_url} != {repo.expected_remote_url})"
            )

        if state.branch is None:
            if mode == "init":
                result.failures.append(f"{repo.id}: detached HEAD")
            else:
                result.warnings.append(f"{repo.id}: detached HEAD")
        elif state.branch != repo.expected_default_branch:
            result.failures.append(
                f"{repo.id}: branch mismatch ({state.branch} != {repo.expected_default_branch})"
            )

        if state.is_dirty:
            result.failures.append(f"{repo.id}: dirty worktree")
    return result
