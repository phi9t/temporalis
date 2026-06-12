from __future__ import annotations

from pathlib import Path

from monoctl.git_probe import inspect_repo, is_git_repo
from monoctl.manifest import load_manifest
from monoctl.models import Manifest, RepoState, RepositorySpec


def resolve_repo_path(manifest_path: Path, repo: RepositorySpec) -> Path:
    repo_path = Path(repo.path)
    if repo_path.is_absolute():
        return repo_path
    return (manifest_path.parent / repo_path).resolve()


def missing_repo_state(repo: RepositorySpec) -> RepoState:
    return RepoState(
        id=repo.id,
        path=repo.path,
        branch=None,
        head="missing",
        describe=None,
        is_dirty=False,
        dirty_summary=[],
        remotes={},
    )


def inspect_manifest(manifest_path: Path) -> tuple[Manifest, list[RepoState]]:
    manifest = load_manifest(manifest_path)
    states: list[RepoState] = []
    for repo in manifest.repos:
        repo_path = resolve_repo_path(manifest_path, repo)
        if not is_git_repo(repo_path):
            states.append(missing_repo_state(repo))
            continue
        states.append(
            inspect_repo(
                repo_path,
                repo_id=repo.id,
                display_path=repo.path,
            )
        )
    return manifest, states
