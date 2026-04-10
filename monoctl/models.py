from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class RepositorySpec:
    id: str
    path: str
    role: str
    upstream_remote: str
    expected_default_branch: str
    criticality: str
    depends_on: list[str] = field(default_factory=list)
    check_commands: list[str] = field(default_factory=list)
    notes: str | None = None
    expected_remote_url: str | None = None


@dataclass(slots=True)
class Manifest:
    repos: list[RepositorySpec]


@dataclass(slots=True)
class RepoState:
    id: str
    path: str
    branch: str | None
    head: str
    describe: str | None
    is_dirty: bool
    dirty_summary: list[str]
    remotes: dict[str, str]


@dataclass(slots=True)
class Snapshot:
    generated_at: str
    repos: list[RepoState]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
