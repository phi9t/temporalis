from __future__ import annotations


def test_inspectl_cli_module_imports() -> None:
    from inspectl.cli import run

    assert callable(run)
