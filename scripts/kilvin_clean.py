#!/usr/bin/env python3
"""Conservatively clean regenerable local Kilvin runtime artifacts."""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KUBECONFIG = REPO_ROOT / "kilvin-py" / "infra" / ".kubeconfig" / "kubeconfig.yaml"
EXTRA_TOOL_DIRS = (REPO_ROOT / ".venv" / "bin", Path("/opt/homebrew/bin"))
TRAINER_REPOSITORY = "localhost:5001/kilvin-trainer"


@dataclasses.dataclass(frozen=True)
class DockerImage:
    repository: str
    tag: str
    image_id: str


def find_command(name: str) -> str | None:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    for directory in EXTRA_TOOL_DIRS:
        candidate = directory / name
        if candidate.exists():
            return str(candidate)
    return None


def resolve_command(cmd: list[str]) -> list[str]:
    resolved = find_command(cmd[0])
    return [resolved or cmd[0], *cmd[1:]]


def run_command(cmd: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(resolve_command(cmd), text=True, capture_output=True, timeout=timeout, check=False)


def docker_images() -> list[DockerImage]:
    result = run_command(
        ["docker", "images", "--format", "{{.Repository}}\t{{.Tag}}\t{{.ID}}"],
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "docker images failed")
    images: list[DockerImage] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            images.append(DockerImage(parts[0], parts[1], parts[2]))
    return images


def active_kilvin_run_ids() -> set[str]:
    if not KUBECONFIG.exists() or find_command("kubectl") is None:
        return set()
    result = run_command(
        [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "-n",
            "kilvin-training",
            "get",
            "pods",
            "-o",
            "json",
        ],
        timeout=30,
    )
    if result.returncode != 0:
        return set()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()
    active: set[str] = set()
    for item in payload.get("items", []):
        phase = item.get("status", {}).get("phase")
        if phase not in {"Pending", "Running"}:
            continue
        run_id = item.get("metadata", {}).get("labels", {}).get("kilvin.run-id")
        if run_id:
            active.add(run_id)
    return active


def select_trainer_images_to_remove(
    images: list[DockerImage],
    *,
    active_run_ids: set[str],
    keep_recent: int,
) -> list[DockerImage]:
    trainer_images = [
        image
        for image in images
        if image.repository == TRAINER_REPOSITORY and image.tag not in {"<none>", "latest"}
    ]
    removable: list[DockerImage] = []
    kept_recent = 0
    for image in trainer_images:
        if image.tag in active_run_ids:
            continue
        if kept_recent < keep_recent:
            kept_recent += 1
            continue
        removable.append(image)
    return removable


def print_disk_report() -> None:
    result = run_command(["docker", "system", "df"], timeout=30)
    if result.returncode == 0:
        print(result.stdout.rstrip())
    else:
        print(result.stderr.strip() or "WARN docker system df failed")
    if find_command("colima") is None:
        return
    vm = run_command(["colima", "ssh", "--", "df", "-h", "/var/lib/docker"], timeout=30)
    if vm.returncode == 0:
        print("\nColima Docker filesystem:")
        print(vm.stdout.rstrip())


def remove_images(images: list[DockerImage], *, dry_run: bool) -> int:
    exit_code = 0
    for image in images:
        ref = f"{image.repository}:{image.tag}"
        if dry_run:
            print(f"DRY-RUN remove {ref} ({image.image_id})")
            continue
        result = run_command(["docker", "image", "rm", ref], timeout=60)
        if result.returncode == 0:
            print(f"removed {ref}")
        else:
            exit_code = 1
            print(f"FAIL remove {ref}: {result.stderr.strip() or result.stdout.strip()}")
    return exit_code


def prune_build_cache(*, dry_run: bool) -> int:
    if dry_run:
        print("DRY-RUN prune Docker builder cache")
        return 0
    result = run_command(["docker", "builder", "prune", "-af"], timeout=300)
    if result.returncode != 0:
        print(f"FAIL builder prune: {result.stderr.strip() or result.stdout.strip()}")
        return 1
    print(result.stdout.rstrip())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show what would be removed")
    parser.add_argument("--keep-recent", type=int, default=2, help="non-active trainer images to keep")
    parser.add_argument(
        "--prune-build-cache",
        action="store_true",
        help="also prune Docker builder cache; this is regenerable but can be expensive",
    )
    args = parser.parse_args(argv)

    print_disk_report()
    active_run_ids = active_kilvin_run_ids()
    to_remove = select_trainer_images_to_remove(
        docker_images(),
        active_run_ids=active_run_ids,
        keep_recent=max(args.keep_recent, 0),
    )
    if not to_remove:
        print("\nNo old Kilvin trainer images selected for removal.")
    else:
        print("\nOld Kilvin trainer images selected for removal:")
        for image in to_remove:
            print(f"  {image.repository}:{image.tag} ({image.image_id})")
    exit_code = remove_images(to_remove, dry_run=args.dry_run)
    if args.prune_build_cache:
        exit_code = max(exit_code, prune_build_cache(dry_run=args.dry_run))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
