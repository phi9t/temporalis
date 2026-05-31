from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "explorer" / "public" / "data"


def load_json(relative: str) -> Any:
    return json.loads((DATA / relative).read_text(encoding="utf-8"))


def print_header(title: str) -> None:
    print(f"== {title} ==")


def iter_refs() -> list[dict[str, Any]]:
    manifest = load_json("lifecycle/kilvin-asyncio-happy-path.json")
    return [ref for node in manifest["nodes"] for ref in node["refs"]]


def print_ref(ref: dict[str, Any]) -> None:
    print(f"- {ref['repo']}:{ref['path']}:{ref['line']} ({ref['label']})")
