from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from monoctl.git_probe import inspect_repo, is_git_repo
from monoctl.manifest import load_manifest
from monoctl.models import Manifest, RepoState, RepositorySpec, Snapshot
from monoctl.render import render_snapshot_markdown


DEFAULT_MANIFEST = Path("constellation/repos.yaml")
DEFAULT_LOCKFILE = Path("constellation/current.lock.json")
DEFAULT_REPORT_DIR = Path("docs/constellation/snapshots")


def _manifest_path(value: str | None) -> Path:
    return Path(value) if value else DEFAULT_MANIFEST


def _resolve_repo_path(manifest_path: Path, repo: RepositorySpec) -> Path:
    repo_path = Path(repo.path)
    if repo_path.is_absolute():
        return repo_path
    return (manifest_path.parent / repo_path).resolve()


def _inspect_manifest(manifest_path: Path) -> tuple[Manifest, list[RepoState]]:
    manifest = load_manifest(manifest_path)
    states: list[RepoState] = []
    for repo in manifest.repos:
        repo_path = _resolve_repo_path(manifest_path, repo)
        if not is_git_repo(repo_path):
            states.append(
                RepoState(
                    id=repo.id,
                    path=repo.path,
                    branch=None,
                    head="missing",
                    describe=None,
                    is_dirty=False,
                    dirty_summary=[],
                    remotes={},
                )
            )
            continue
        states.append(
            inspect_repo(
                repo_path,
                repo_id=repo.id,
                display_path=repo.path,
            )
        )
    return manifest, states


def _doctor_findings(
    manifest_path: Path, manifest: Manifest, states: list[RepoState]
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    for repo, state in zip(manifest.repos, states, strict=True):
        repo_path = _resolve_repo_path(manifest_path, repo)
        if not repo_path.exists():
            failures.append(f"{repo.id}: missing path {repo.path}")
            continue
        if not is_git_repo(repo_path):
            failures.append(f"{repo.id}: path is not a git repo ({repo.path})")
            continue
        remote_url = state.remotes.get(repo.upstream_remote)
        if remote_url is None:
            failures.append(f"{repo.id}: missing upstream remote {repo.upstream_remote}")
        elif repo.expected_remote_url and remote_url != repo.expected_remote_url:
            failures.append(
                f"{repo.id}: remote {repo.upstream_remote} URL mismatch "
                f"({remote_url} != {repo.expected_remote_url})"
            )
        if state.branch and state.branch != repo.expected_default_branch:
            failures.append(
                f"{repo.id}: branch mismatch ({state.branch} != {repo.expected_default_branch})"
            )
        if state.branch is None:
            warnings.append(f"{repo.id}: detached HEAD")
        if state.is_dirty:
            failures.append(f"{repo.id}: dirty worktree")
    return failures, warnings


def _print_status(states: list[RepoState]) -> None:
    for state in states:
        branch = state.branch or "detached"
        dirty = "dirty" if state.is_dirty else "clean"
        describe = state.describe or "n/a"
        remote_summary = ", ".join(
            f"{name}={url}" for name, url in sorted(state.remotes.items())
        ) or "none"
        print(
            f"{state.id}: branch={branch} head={state.head} "
            f"describe={describe} remotes=[{remote_summary}] state={dirty}"
        )


def _snapshot(states: list[RepoState]) -> Snapshot:
    return Snapshot(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        repos=states,
    )


def _write_snapshot(snapshot: Snapshot, lockfile: Path, report_dir: Path) -> Path:
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lockfile.write_text(json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{snapshot.generated_at.replace(':', '').replace('-', '')}.md"
    report_path.write_text(render_snapshot_markdown(snapshot), encoding="utf-8")
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monoctl")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", parents=[common])
    subparsers.add_parser("status", parents=[common])
    subparsers.add_parser("doctor", parents=[common])
    snapshot = subparsers.add_parser("snapshot", parents=[common])
    snapshot.add_argument("--lockfile", default=str(DEFAULT_LOCKFILE))
    snapshot.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest_path = _manifest_path(args.manifest)
    manifest, states = _inspect_manifest(manifest_path)

    if args.command == "list":
        for repo in manifest.repos:
            print(f"{repo.id}\t{repo.path}\t{repo.role}\t{repo.criticality}")
        return 0
    if args.command == "status":
        _print_status(states)
        return 0
    if args.command == "doctor":
        failures, warnings = _doctor_findings(manifest_path, manifest, states)
        for warning in warnings:
            print(f"WARNING: {warning}")
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1 if failures else 0
    if args.command == "snapshot":
        snapshot = _snapshot(states)
        report_path = _write_snapshot(
            snapshot,
            lockfile=Path(args.lockfile),
            report_dir=Path(args.report_dir),
        )
        print(f"Wrote {args.lockfile}")
        print(f"Wrote {report_path}")
        return 0
    parser.error(f"unknown command {args.command}")
    return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
