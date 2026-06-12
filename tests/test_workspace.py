from __future__ import annotations

from pathlib import Path

from monoctl.models import RepositorySpec
from monoctl.workspace import inspect_manifest, missing_repo_state, resolve_repo_path

from tests.helpers import init_git_repo


def test_resolve_repo_path_uses_manifest_directory_for_relative_paths(tmp_path: Path) -> None:
    manifest_path = tmp_path / ".monorepo" / "repos.yaml"
    repo = RepositorySpec(
        id="temporal",
        path="../temporal",
        role="engine",
        upstream_remote="origin",
        expected_default_branch="main",
        criticality="high",
    )

    assert resolve_repo_path(manifest_path, repo) == (tmp_path / "temporal").resolve()


def test_missing_repo_state_preserves_manifest_identity() -> None:
    repo = RepositorySpec(
        id="temporal",
        path="../temporal",
        role="engine",
        upstream_remote="origin",
        expected_default_branch="main",
        criticality="high",
    )

    state = missing_repo_state(repo)

    assert state.id == "temporal"
    assert state.path == "../temporal"
    assert state.branch is None
    assert state.head == "missing"
    assert state.remotes == {}


def test_inspect_manifest_returns_loaded_manifest_and_repo_states(tmp_path: Path) -> None:
    repo_path = tmp_path / "sdk-python"
    commit = init_git_repo(repo_path)
    manifest_path = tmp_path / "repos.yaml"
    manifest_path.write_text(
        f"""
repos:
  - id: sdk-python
    path: {repo_path}
    role: sdk
    upstream_remote: origin
    expected_default_branch: main
    criticality: critical
  - id: missing
    path: {tmp_path / "missing"}
    role: sdk
    upstream_remote: origin
    expected_default_branch: main
    criticality: low
""".strip()
        + "\n",
        encoding="utf-8",
    )

    manifest, states = inspect_manifest(manifest_path)

    assert [repo.id for repo in manifest.repos] == ["sdk-python", "missing"]
    assert states[0].id == "sdk-python"
    assert states[0].head == commit
    assert states[1].id == "missing"
    assert states[1].head == "missing"
