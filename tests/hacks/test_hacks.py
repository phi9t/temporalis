from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HACKS = ROOT / "hacks"
sys.path.insert(0, str(HACKS))
DEFAULT_HACKS = [
    "001_source_map.py",
    "002_lifecycle_manifest.py",
    "003_task_queue_polling.py",
    "004_history_replay.py",
    "005_control_paths.py",
]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_hacks_have_metadata() -> None:
    for name in DEFAULT_HACKS:
        module = load_module(HACKS / name)
        assert isinstance(module.GUIDE_ANCHOR, str)
        assert module.GUIDE_ANCHOR
        assert isinstance(module.SUMMARY, str)
        assert module.SUMMARY


def test_default_hacks_run_and_print_expected_markers() -> None:
    expected = {
        "001_source_map.py": "Temporal source map",
        "002_lifecycle_manifest.py": "Kilvin asyncio happy path",
        "003_task_queue_polling.py": "Task queue polling",
        "004_history_replay.py": "History and replay",
        "005_control_paths.py": "Control paths",
    }
    for name, marker in expected.items():
        completed = subprocess.run(
            [sys.executable, str(HACKS / name)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        assert marker in completed.stdout
