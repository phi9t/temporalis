#!/usr/bin/env python3
from __future__ import annotations

from _common import load_json, print_header

GUIDE_ANCHOR = "retry-and-failure-handling"
SUMMARY = "Print control-path overlays for retry, replay, pause/resume, heartbeat cancellation, and sticky eviction."


def main() -> None:
    print_header("Control paths")
    index = load_json("control-paths/index.json")
    for entry in index:
        scenario = load_json(entry["manifest"])
        print(f"- {scenario['label']}: {scenario['summary']}")
        for detail in scenario.get("details", []):
            print(f"  detail: {detail}")


if __name__ == "__main__":
    main()
