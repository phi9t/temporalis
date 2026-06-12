from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def tracked_files(prefix: str) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", prefix],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def tracked_files_under(prefix: str) -> list[str]:
    normalized = prefix.rstrip("/")
    return [
        line
        for line in tracked_files(normalized)
        if line == normalized or line.startswith(normalized + "/")
    ]


def test_public_docs_exist() -> None:
    for path in [
        "docs/quickstart.md",
        "docs/runtime-proof.md",
        "docs/release-checklist.md",
        "docs/source-grounding.md",
    ]:
        assert (ROOT / path).is_file(), path


def test_public_readme_leads_with_three_layer_release_story() -> None:
    body = read("README.md")
    assert "Temporalis" in body
    assert "https://phi9t.github.io/temporalis/" in body
    assert "Tier 0" in body
    assert "Tier 1" in body
    assert "Tier 2" in body
    assert "make quickstart" in body
    assert "make runtime-proof" in body
    assert "64 A100" in body
    assert "FineWeb" in body
    assert "laptop" in body.lower()


def test_public_docs_do_not_advertise_hidden_hackers_guide_ui() -> None:
    combined = "\n".join(
        [
            read("README.md"),
            read("explorer/README.md"),
            read("docs/quickstart.md"),
        ]
    )
    forbidden = [
        "rendered Hacker's Guide alongside the Deep Dive view",
        "Hacker's Guide mode",
        "Hacker's Guide tab",
        "Lifecycle, Control Paths, Kilvin Internals, and the Hacker's Guide",
        "links to its HACKERS_GUIDE.md section",
    ]
    for phrase in forbidden:
        assert phrase not in combined


def test_makefile_exposes_public_release_targets() -> None:
    makefile = read("Makefile")
    for target in [
        "quickstart:",
        "quickstart-check:",
        "verify-release:",
        "runtime-proof:",
    ]:
        assert target in makefile


def test_agentic_release_artifacts_are_tracked_under_agents() -> None:
    assert tracked_files_under(".agent") == []
    tracked = set(tracked_files_under(".agents"))
    assert ".agents/checks/control_path_check.py" in tracked
    assert ".agents/notes/release-learning-session.md" in tracked
