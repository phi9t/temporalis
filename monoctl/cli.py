from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from monoctl.models import Manifest, RepoState, Snapshot
from monoctl.render import render_snapshot_markdown
from monoctl.validation import validate_workspace
from monoctl.workspace import inspect_manifest, resolve_repo_path


DEFAULT_MANIFEST = Path(".monorepo/repos.yaml")
DEFAULT_LOCKFILE = Path(".monorepo/current.lock.json")
DEFAULT_REPORT_DIR = Path("docs/.monorepo/snapshots")


def _manifest_path(value: str | None) -> Path:
    return Path(value) if value else DEFAULT_MANIFEST


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


def _run_git_command(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _init_repos(manifest_path: Path, manifest: Manifest, states: list[RepoState]) -> int:
    validation = validate_workspace(manifest_path, manifest, states, mode="init")
    for failure in validation.failures:
        print(f"FAIL: {failure}")
    if validation.failures:
        return 1

    for repo, state in zip(manifest.repos, states, strict=True):
        repo_path = resolve_repo_path(manifest_path, repo)
        if not repo_path.exists():
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            command = [
                "git",
                "clone",
                "--branch",
                repo.expected_default_branch,
                repo.expected_remote_url or "",
                str(repo_path),
            ]
            try:
                _run_git_command(command, cwd=manifest_path.parent.resolve())
            except subprocess.CalledProcessError as exc:
                print(f"FAIL: {repo.id}: git command failed with exit {exc.returncode}")
                return 1
            print(f"Cloned {repo.id} -> {repo.path}")
            continue
        command = [
            "git",
            "pull",
            "--ff-only",
            repo.upstream_remote,
            repo.expected_default_branch,
        ]
        try:
            _run_git_command(command, cwd=repo_path)
        except subprocess.CalledProcessError as exc:
            print(f"FAIL: {repo.id}: git command failed with exit {exc.returncode}")
            return 1
        print(f"Pulled {repo.id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monoctl")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", parents=[common])
    subparsers.add_parser("status", parents=[common])
    subparsers.add_parser("doctor", parents=[common])
    subparsers.add_parser("init", parents=[common])
    snapshot = subparsers.add_parser("snapshot", parents=[common])
    snapshot.add_argument("--lockfile", default=str(DEFAULT_LOCKFILE))
    snapshot.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest_path = _manifest_path(args.manifest)
    manifest, states = inspect_manifest(manifest_path)

    if args.command == "list":
        for repo in manifest.repos:
            print(f"{repo.id}\t{repo.path}\t{repo.role}\t{repo.criticality}")
        return 0
    if args.command == "status":
        _print_status(states)
        return 0
    if args.command == "doctor":
        validation = validate_workspace(manifest_path, manifest, states, mode="doctor")
        for warning in validation.warnings:
            print(f"WARNING: {warning}")
        for failure in validation.failures:
            print(f"FAIL: {failure}")
        return 1 if validation.failures else 0
    if args.command == "init":
        return _init_repos(manifest_path, manifest, states)
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
