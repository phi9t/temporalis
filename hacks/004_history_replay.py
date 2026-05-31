#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "history-as-source-of-truth-and-replay"
SUMMARY = "Show how History, sdk-core, and Python activation refs explain replay."

REPLAY_NODES = {"history-service", "core-worker", "workflow-activation"}


def main() -> None:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    print_header("History and replay")
    for node in manifest["nodes"]:
        if node["id"] in REPLAY_NODES:
            print(f"- {node['label']}: {node['notes']}")
    print("Replay rule: workflow code re-executes deterministically; activity side effects do not.")


if __name__ == "__main__":
    main()
