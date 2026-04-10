from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from inspectl.models import RuntimeConfig


class LocalServerManager:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.runtime_dir = config.local_state_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_file = self.runtime_dir / "temporal.sqlite"
        self.state_file = self.runtime_dir / "server.json"

    def build_command(self, *, port: int) -> list[str]:
        return [
            self.config.temporal_cli_path,
            "server",
            "start-dev",
            "--headless",
            "--port",
            str(port),
            "--http-port",
            "0",
            "--metrics-port",
            "0",
            "--db-filename",
            str(self.db_file),
        ]

    def write_state(self, *, pid: int, target: str) -> None:
        payload = {
            "pid": pid,
            "target": target,
            "db_filename": str(self.db_file),
        }
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def read_state(self) -> dict[str, Any] | None:
        if not self.state_file.exists():
            return None
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def is_pid_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def is_runtime_state_valid(self, state: dict[str, Any] | None) -> bool:
        if not isinstance(state, dict):
            return False

        pid = state.get("pid")
        target = state.get("target")
        db_filename = state.get("db_filename")
        if not isinstance(pid, int) or pid <= 0:
            return False
        if target != f"{self.config.host}:{self.config.port}":
            return False
        if not isinstance(db_filename, str):
            return False
        if Path(db_filename).resolve() != self.db_file.resolve():
            return False
        return self.is_pid_running(pid)

    def start(self) -> dict[str, Any]:
        process = subprocess.Popen(
            self.build_command(port=self.config.port),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        details = {
            "pid": process.pid,
            "target": f"{self.config.host}:{self.config.port}",
        }
        self.write_state(**details)
        return details
