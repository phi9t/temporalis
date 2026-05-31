#!/usr/bin/env python3
from __future__ import annotations

import os

GUIDE_ANCHOR = "hands-on-hacks"
SUMMARY = "Optional heavier local Temporal run; skipped unless TEMPORALIS_RUN_OPTIONAL_HACK=1."


def main() -> int:
    if os.environ.get("TEMPORALIS_RUN_OPTIONAL_HACK") != "1":
        print("Optional local run skipped. Set TEMPORALIS_RUN_OPTIONAL_HACK=1 to opt in.")
        return 0
    print("Optional local Temporal run is intentionally explicit; wire this to the local runtime when needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
