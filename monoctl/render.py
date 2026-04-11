from __future__ import annotations

from monoctl.models import Snapshot


def render_snapshot_markdown(snapshot: Snapshot) -> str:
    lines = [
        "# Monorepo Snapshot",
        "",
        f"Generated: {snapshot.generated_at}",
        "",
        "| Repo | Path | Branch | Head | State |",
        "| --- | --- | --- | --- | --- |",
    ]
    for repo in snapshot.repos:
        branch = repo.branch or "detached"
        state = "dirty" if repo.is_dirty else "clean"
        lines.append(f"| {repo.id} | {repo.path} | {branch} | {repo.head} | {state} |")
    return "\n".join(lines) + "\n"
