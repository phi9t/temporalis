from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def init_git_repo(path: Path, branch: str = "main") -> str:
    path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-b", branch], cwd=path)
    run(["git", "config", "user.name", "Test User"], cwd=path)
    run(["git", "config", "user.email", "test@example.com"], cwd=path)
    (path / "README.md").write_text("# fixture\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=path)
    run(["git", "commit", "-m", "init"], cwd=path)
    run(
        ["git", "remote", "add", "origin", f"git@github.com:example/{path.name}.git"],
        cwd=path,
    )
    return run(["git", "rev-parse", "HEAD"], cwd=path).stdout.strip()
