from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kilvin-py"))

from kilvin_py.config import KilvinSettings  # noqa: E402
from kilvin_py.proc import SubprocessFailed, run_logged  # noqa: E402


def test_settings_defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = KilvinSettings.load()
    assert settings.temporal_address == "localhost:7233"
    assert settings.allocator_url == "http://localhost:7070"
    assert settings.registry == "localhost:5001"
    assert settings.namespace == "kilvin-training"
    assert settings.trainer_dir.name == "trainer"
    assert settings.kubeconfig_path.name == "kubeconfig.yaml"

    monkeypatch.setenv("KILVIN_ALLOCATOR_URL", "http://allocator:7070")
    assert KilvinSettings.load().allocator_url == "http://allocator:7070"


def test_run_logged_captures_output_and_raises_with_tail() -> None:
    lines = asyncio.run(run_logged([sys.executable, "-c", "print('a'); print('b')"], label="ok"))
    assert lines == ["a", "b"]

    with pytest.raises(SubprocessFailed) as err:
        asyncio.run(
            run_logged(
                [sys.executable, "-c", "print('boom-detail'); raise SystemExit(3)"],
                label="fails",
            )
        )
    assert "boom-detail" in str(err.value)
    assert "exit 3" in str(err.value)
