#!/usr/bin/env python3
"""Poll GitHub Pages until the Kilvin generated data is visibly updated."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "https://phi9t.github.io/temporalis/data/kilvin/internals.json"
DEFAULT_EXPECTED = ("laptop scale", "uv lock --check", "local allocator", "k3s")


def missing_expected_strings(body: str, expected: tuple[str, ...] = DEFAULT_EXPECTED) -> list[str]:
    return [needle for needle in expected if needle not in body]


def cache_busted_url(url: str) -> str:
    separator = "&" if urllib.parse.urlparse(url).query else "?"
    return f"{url}{separator}ts={int(time.time())}"


def fetch_text(url: str, timeout: float = 20.0) -> str:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def poll_pages(url: str, *, attempts: int, interval: float) -> int:
    last_missing: list[str] = []
    for attempt in range(1, attempts + 1):
        current_url = cache_busted_url(url)
        try:
            body = fetch_text(current_url)
        except (urllib.error.URLError, TimeoutError) as err:
            print(f"WARN attempt {attempt}/{attempts}: HTTP fetch failed: {err}")
            if attempt < attempts:
                time.sleep(interval)
            continue

        last_missing = missing_expected_strings(body)
        if not last_missing:
            print(f"PASS Pages content is updated: {url}")
            return 0

        print(
            "WAIT attempt "
            f"{attempt}/{attempts}: missing {', '.join(repr(item) for item in last_missing)}"
        )
        if attempt < attempts:
            time.sleep(interval)

    if last_missing:
        print(f"FAIL Pages content did not include: {', '.join(repr(item) for item in last_missing)}")
    else:
        print("FAIL Pages content could not be fetched.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--attempts", type=int, default=20)
    parser.add_argument("--interval", type=float, default=15.0)
    args = parser.parse_args(argv)
    return poll_pages(args.url, attempts=args.attempts, interval=args.interval)


if __name__ == "__main__":
    sys.exit(main())
