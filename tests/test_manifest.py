from __future__ import annotations

from pathlib import Path

from monoctl.manifest import load_manifest


def test_load_manifest_reads_curated_repo_metadata(tmp_path: Path) -> None:
    manifest = tmp_path / "repos.yaml"
    manifest.write_text(
        """
repos:
  - id: sdk-core
    path: sdk-core
    role: shared runtime
    upstream_remote: origin
    expected_default_branch: master
    criticality: high
    depends_on:
      - temporal
    check_commands:
      - cargo test -p sdk-core
""".strip()
        + "\n",
        encoding="utf-8",
    )

    loaded = load_manifest(manifest)

    assert [repo.id for repo in loaded.repos] == ["sdk-core"]
    assert loaded.repos[0].expected_default_branch == "master"
    assert loaded.repos[0].depends_on == ["temporal"]
    assert loaded.repos[0].check_commands == ["cargo test -p sdk-core"]
