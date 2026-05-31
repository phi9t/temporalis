#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "happy-path-start-workflow-to-first-activation"
SUMMARY = "Walk the Kilvin asyncio happy-path lifecycle manifest in phase order."


def main() -> None:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    print_header(manifest["label"])
    nodes = {node["id"]: node["label"] for node in manifest["nodes"]}
    for phase in manifest["phases"]:
        labels = ", ".join(nodes[node_id] for node_id in phase["node_ids"])
        print(f"- {phase['label']}: {labels}")


if __name__ == "__main__":
    main()
