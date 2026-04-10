from __future__ import annotations

from pathlib import Path

from monoctl.git_probe import inspect_repo

from tests.helpers import init_git_repo


def test_inspect_repo_reports_branch_head_and_remote(tmp_path: Path) -> None:
    repo_path = tmp_path / "sdk-python"
    commit = init_git_repo(repo_path, branch="main")

    state = inspect_repo(repo_path)

    assert state.branch == "main"
    assert state.head == commit
    assert state.is_dirty is False
    assert state.remotes == {"origin": "git@github.com:example/sdk-python.git"}
