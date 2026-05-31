from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoInfo:
    id: str
    path: str
    branch: str
    head: str
    remote: str


def load_repos(repo_root: Path) -> dict[str, RepoInfo]:
    raw = json.loads((repo_root / ".monorepo" / "current.lock.json").read_text(encoding="utf-8"))
    repos: dict[str, RepoInfo] = {}
    for repo in raw["repos"]:
        remotes = repo.get("remotes", {})
        origin = remotes.get("origin", "")
        repos[repo["id"]] = RepoInfo(
            id=repo["id"],
            path=repo["path"],
            branch=repo.get("branch") or "detached",
            head=repo["head"],
            remote=origin,
        )
    return repos


def repo_abs_path(repo_root: Path, repo: RepoInfo) -> Path:
    candidates = [
        repo_root / repo.path,
        repo_root / Path(repo.path).name,
        repo_root / ".monorepo" / repo.path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def github_url(remote: str) -> str:
    if remote.startswith("git@github.com:"):
        return "https://github.com/" + remote.removeprefix("git@github.com:").removesuffix(".git")
    return remote.removesuffix(".git")


def resolve_line(base: Path, rel_path: str, symbol: str) -> int:
    path = base / rel_path
    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        if symbol in line:
            return idx
    raise ValueError(f"symbol {symbol!r} not found in {path}")
