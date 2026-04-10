from __future__ import annotations

from monoctl.models import RepoState, Snapshot
from monoctl.render import render_snapshot_markdown


def test_render_snapshot_markdown_includes_repo_summary() -> None:
    snapshot = Snapshot(
        generated_at="2026-04-10T12:00:00Z",
        repos=[
            RepoState(
                id="temporal",
                path="temporal",
                branch="main",
                head="abc123",
                describe="v1.29.0",
                is_dirty=False,
                dirty_summary=[],
                remotes={"origin": "git@github.com:temporalio/temporal.git"},
            )
        ],
    )

    rendered = render_snapshot_markdown(snapshot)

    assert "# Constellation Snapshot" in rendered
    assert "Generated: 2026-04-10T12:00:00Z" in rendered
    assert "| temporal | temporal | main | abc123 | clean |" in rendered
