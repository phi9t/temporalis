#!/usr/bin/env python3
from __future__ import annotations

from _common import iter_refs, print_header, print_ref

GUIDE_ANCHOR = "where-to-inspect-source-next"
SUMMARY = "Print the source anchors used by the Temporal guide and explorer."


def main() -> None:
    print_header("Temporal source map")
    for ref in iter_refs():
        print_ref(ref)


if __name__ == "__main__":
    main()
