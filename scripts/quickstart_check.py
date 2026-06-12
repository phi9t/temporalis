#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "explorer" / "public" / "data"

REQUIRED_DATA_FILES = [
    "lifecycle/kilvin-asyncio-happy-path.json",
    "control-paths/index.json",
    "kilvin/internals.json",
    "repos.json",
]

DEFAULT_HACKS = {
    "001_source_map.py": "Temporal source map",
    "002_lifecycle_manifest.py": "Kilvin asyncio happy path",
    "003_task_queue_polling.py": "Task queue polling",
    "004_history_replay.py": "History and replay",
    "005_control_paths.py": "Control paths",
}


def load_json(relative_path: str) -> dict | list:
    return json.loads((DATA / relative_path).read_text(encoding="utf-8"))


def load_json_checked(relative_path: str, failures: list[str]) -> dict | list | None:
    try:
        return load_json(relative_path)
    except FileNotFoundError:
        failures.append(f"missing generated data: {relative_path}")
    except json.JSONDecodeError as error:
        failures.append(f"generated data is invalid JSON: {relative_path}: {error}")
    return None


def items_missing_refs(items: Iterable[dict]) -> list[str]:
    missing: list[str] = []
    for item in items:
        if not item.get("refs"):
            missing.append(str(item.get("id", "<missing id>")))
    return missing


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def check_required_files(failures: list[str]) -> None:
    for relative_path in REQUIRED_DATA_FILES:
        require((DATA / relative_path).is_file(), f"missing generated data: {relative_path}", failures)


def check_lifecycle(failures: list[str]) -> None:
    lifecycle = load_json_checked("lifecycle/kilvin-asyncio-happy-path.json", failures)
    if lifecycle is None:
        return
    if not isinstance(lifecycle, dict):
        failures.append("lifecycle manifest is not an object")
        return
    calls = lifecycle.get("calls", [])
    require(bool(calls), "lifecycle manifest has no calls", failures)
    missing = items_missing_refs(calls)
    require(not missing, f"lifecycle calls missing refs: {', '.join(missing)}", failures)


def check_control_paths(failures: list[str]) -> None:
    index = load_json_checked("control-paths/index.json", failures)
    if index is None:
        return
    if not isinstance(index, list):
        failures.append("control-path index is not a list")
        return
    require(bool(index), "control-path index is empty", failures)
    for entry in index:
        if not isinstance(entry, dict):
            failures.append("control-path entry is not an object")
            continue

        slug = entry.get("slug")
        manifest = entry.get("manifest")
        if not isinstance(slug, str):
            failures.append("control-path entry missing string slug")
        if not isinstance(manifest, str):
            label = slug if isinstance(slug, str) else "<missing slug>"
            failures.append(f"control-path entry has non-string manifest: {label}")
        if not isinstance(slug, str) or not isinstance(manifest, str):
            continue

        scenario = load_json_checked(manifest, failures)
        if scenario is None:
            continue
        if not isinstance(scenario, dict):
            failures.append(f"control scenario is not an object: {slug}")
            continue
        steps = scenario.get("steps", [])
        require(bool(steps), f"control scenario has no steps: {slug}", failures)
        missing = items_missing_refs(steps)
        require(not missing, f"control steps missing refs in {slug}: {', '.join(missing)}", failures)


def check_kilvin_internals(failures: list[str]) -> None:
    internals = load_json_checked("kilvin/internals.json", failures)
    if internals is None:
        return
    if not isinstance(internals, dict):
        failures.append("Kilvin Internals manifest is not an object")
        return
    expected_labels = [
        "Interpret training intent",
        "Build image and deps",
        "Find quota and reserve resources",
        "Materialize job spec",
        "Submit Kubernetes job",
        "Monitor training",
    ]
    got_labels = [step.get("label") for step in internals.get("steps", [])]
    require(got_labels == expected_labels, f"unexpected Kilvin Internals labels: {got_labels}", failures)
    workflow_copy = " ".join([internals.get("workflow", {}).get("summary", ""), *internals.get("workflow", {}).get("details", [])])
    for phrase in ["64 A100", "FineWeb", "laptop scale", "tiny CPU GPT-2"]:
        require(phrase in workflow_copy, f"Kilvin Internals workflow copy missing {phrase!r}", failures)


def run_hacks(failures: list[str]) -> None:
    for script, marker in DEFAULT_HACKS.items():
        completed = subprocess.run(
            [sys.executable, str(ROOT / "hacks" / script)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            failures.append(f"{script} exited {completed.returncode}: {completed.stderr.strip()}")
        elif marker not in completed.stdout:
            failures.append(f"{script} output did not include {marker!r}")


def main() -> int:
    failures: list[str] = []
    check_required_files(failures)
    if not failures:
        check_lifecycle(failures)
        check_control_paths(failures)
        check_kilvin_internals(failures)
        run_hacks(failures)

    if failures:
        print("Quickstart check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Quickstart check passed.")
    print("Next: run `make explorer-dev` and open the local Vite URL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
