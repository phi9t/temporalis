from __future__ import annotations

from pathlib import Path

from monoctl.models import Manifest, RepoState, RepositorySpec
from monoctl.validation import validate_workspace


def repo_spec(
    *,
    expected_remote_url: str | None = "git@github.com:example/sdk-python.git",
) -> RepositorySpec:
    return RepositorySpec(
        id="sdk-python",
        path="sdk-python",
        role="sdk",
        upstream_remote="origin",
        expected_remote_url=expected_remote_url,
        expected_default_branch="main",
        criticality="critical",
    )


def repo_state(
    *,
    branch: str | None = "main",
    is_dirty: bool = False,
    remotes: dict[str, str] | None = None,
) -> RepoState:
    return RepoState(
        id="sdk-python",
        path="sdk-python",
        branch=branch,
        head="abc123",
        describe="abc123",
        is_dirty=is_dirty,
        dirty_summary=[" M README.md"] if is_dirty else [],
        remotes=remotes or {"origin": "git@github.com:example/sdk-python.git"},
    )


def test_doctor_fails_missing_repo_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "repos.yaml"
    result = validate_workspace(
        manifest_path,
        Manifest(repos=[repo_spec()]),
        [repo_state()],
        mode="doctor",
    )

    assert result.failures == ["sdk-python: missing path sdk-python"]
    assert result.warnings == []


def test_doctor_warns_on_detached_head(tmp_path: Path) -> None:
    repo_path = tmp_path / "sdk-python"
    repo_path.mkdir()
    manifest_path = tmp_path / "repos.yaml"

    result = validate_workspace(
        manifest_path,
        Manifest(repos=[repo_spec()]),
        [repo_state(branch=None)],
        mode="doctor",
    )

    assert result.failures == []
    assert result.warnings == ["sdk-python: detached HEAD"]


def test_init_allows_missing_repo_when_clone_url_is_present(tmp_path: Path) -> None:
    manifest_path = tmp_path / "repos.yaml"

    result = validate_workspace(
        manifest_path,
        Manifest(repos=[repo_spec()]),
        [repo_state()],
        mode="init",
    )

    assert result.failures == []
    assert result.warnings == []


def test_init_rejects_missing_repo_without_clone_url(tmp_path: Path) -> None:
    manifest_path = tmp_path / "repos.yaml"

    result = validate_workspace(
        manifest_path,
        Manifest(repos=[repo_spec(expected_remote_url=None)]),
        [repo_state()],
        mode="init",
    )

    assert result.failures == ["sdk-python: missing expected_remote_url for clone"]
    assert result.warnings == []


def test_init_rejects_dirty_detached_wrong_branch_and_wrong_remote(tmp_path: Path) -> None:
    repo_path = tmp_path / "sdk-python"
    repo_path.mkdir()
    manifest_path = tmp_path / "repos.yaml"
    manifest = Manifest(
        repos=[
            repo_spec(),
            RepositorySpec(
                id="sdk-core",
                path="sdk-core",
                role="shared runtime",
                upstream_remote="origin",
                expected_remote_url="git@github.com:example/sdk-core.git",
                expected_default_branch="main",
                criticality="critical",
            ),
            RepositorySpec(
                id="sdk-go",
                path="sdk-go",
                role="sdk",
                upstream_remote="origin",
                expected_remote_url="git@github.com:example/sdk-go.git",
                expected_default_branch="main",
                criticality="critical",
            ),
            RepositorySpec(
                id="temporal",
                path="temporal",
                role="engine",
                upstream_remote="origin",
                expected_remote_url="git@github.com:example/temporal.git",
                expected_default_branch="main",
                criticality="high",
            ),
        ]
    )
    for relative_path in ("sdk-core", "sdk-go", "temporal"):
        (tmp_path / relative_path).mkdir()

    result = validate_workspace(
        manifest_path,
        manifest,
        [
            repo_state(is_dirty=True),
            RepoState(
                id="sdk-core",
                path="sdk-core",
                branch=None,
                head="def456",
                describe="def456",
                is_dirty=False,
                dirty_summary=[],
                remotes={"origin": "git@github.com:example/sdk-core.git"},
            ),
            RepoState(
                id="sdk-go",
                path="sdk-go",
                branch="feature",
                head="ghi789",
                describe="ghi789",
                is_dirty=False,
                dirty_summary=[],
                remotes={"origin": "git@github.com:example/sdk-go.git"},
            ),
            RepoState(
                id="temporal",
                path="temporal",
                branch="main",
                head="jkl012",
                describe="jkl012",
                is_dirty=False,
                dirty_summary=[],
                remotes={"origin": "git@github.com:example/wrong.git"},
            ),
        ],
        mode="init",
    )

    assert result.failures == [
        "sdk-python: dirty worktree",
        "sdk-core: detached HEAD",
        "sdk-go: branch mismatch (feature != main)",
        "temporal: remote origin URL mismatch "
        "(git@github.com:example/wrong.git != git@github.com:example/temporal.git)",
    ]
    assert result.warnings == []
