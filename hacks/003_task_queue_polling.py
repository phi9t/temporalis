#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "workflow-task-polling-matching---sdk-core---bridge---python"
SUMMARY = "Trace Matching -> sdk-core -> bridge -> Python workflow-task polling."

POLLING_NODES = {"python-worker", "bridge-worker", "core-worker", "matching-service"}


def main() -> None:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    print_header("Task queue polling")
    for node in manifest["nodes"]:
        if node["id"] not in POLLING_NODES:
            continue
        print(f"- {node['label']}: {node['summary']}")
        for ref in node["refs"]:
            print(f"  source: {ref['repo']}:{ref['path']}:{ref['line']}")


if __name__ == "__main__":
    main()
