from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from inspectl.local_server import LocalServerManager
from inspectl.models import RuntimeConfig


def test_local_server_builds_temporal_start_dev_command(tmp_path: Path) -> None:
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl")
    manager = LocalServerManager(config)

    command = manager.build_command(port=7233)

    assert command[:3] == ["temporal", "server", "start-dev"]
    assert "--headless" in command
    assert "--db-filename" in command
    assert str(tmp_path / ".inspectl" / "runtime" / "temporal.sqlite") in command


@patch("inspectl.local_server.subprocess.Popen")
def test_local_server_start_persists_runtime_metadata(
    popen: Mock, tmp_path: Path
) -> None:
    popen.return_value.pid = 4242
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl")
    manager = LocalServerManager(config)

    details = manager.start()

    popen.assert_called_once()
    assert details == {"pid": 4242, "target": "127.0.0.1:7233"}
    assert manager.read_state() == {
        "pid": 4242,
        "target": "127.0.0.1:7233",
        "db_filename": str(tmp_path / ".inspectl" / "runtime" / "temporal.sqlite"),
    }


@patch("inspectl.local_server.os.kill", side_effect=ProcessLookupError)
def test_local_server_rejects_stale_pid(
    _kill: Mock, tmp_path: Path
) -> None:
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl")
    manager = LocalServerManager(config)

    assert (
        manager.is_runtime_state_valid(
            {
                "pid": 99999,
                "target": "127.0.0.1:7233",
                "db_filename": str(manager.db_file),
            }
        )
        is False
    )


@patch("inspectl.local_server.os.kill")
def test_local_server_rejects_mismatched_workspace_db(
    _kill: Mock, tmp_path: Path
) -> None:
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl")
    manager = LocalServerManager(config)

    assert (
        manager.is_runtime_state_valid(
            {
                "pid": 4242,
                "target": "127.0.0.1:7233",
                "db_filename": str(tmp_path / "someone-else.sqlite"),
            }
        )
        is False
    )
