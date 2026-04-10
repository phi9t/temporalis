from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import threading
from typing import Any

from inspectl.models import PipelineState


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    run_id: str
    level: str
    event: str
    message: str
    step: str | None = None
    attempt: int | None = None
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "level": self.level,
            "event": self.event,
            "message": self.message,
            "step": self.step,
            "attempt": self.attempt,
            "data": self.data,
        }


class RunSession:
    def __init__(self, run_id: str, root_dir: Path) -> None:
        self.run_id = run_id
        self.root = root_dir / run_id
        self.snapshots = self.root / "state_snapshots"
        self._lock = threading.Lock()
        self._counter = 0
        self._fp: Any | None = None
        self._enabled = False
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self.snapshots.mkdir(parents=True, exist_ok=True)
            self._counter = self._next_snapshot_index()
            self._fp = (self.root / "session.jsonl").open("a", encoding="utf-8", buffering=1)
            self._enabled = True
        except (OSError, TypeError, ValueError):
            self._fp = None
            self._enabled = False

    def _next_snapshot_index(self) -> int:
        max_index = 0
        try:
            for path in self.snapshots.glob("*.json"):
                prefix = path.name.split("_", 1)[0]
                if len(prefix) == 3 and prefix.isdigit():
                    max_index = max(max_index, int(prefix))
        except (OSError, ValueError):
            return 0
        return max_index

    def record(
        self,
        *,
        level: str,
        event: str,
        message: str,
        step: str | None = None,
        attempt: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        entry = LogEntry(
            timestamp=_timestamp(),
            run_id=self.run_id,
            level=level,
            event=event,
            message=message,
            step=step,
            attempt=attempt,
            data=data,
        )
        if not self._enabled or self._fp is None:
            return
        try:
            payload = json.dumps(entry.to_dict(), ensure_ascii=False)
            with self._lock:
                self._fp.write(payload + "\n")
        except (OSError, TypeError, ValueError):
            return

    def snapshot(self, *, step_name: str, state: PipelineState) -> Path:
        if not self._enabled:
            return self.snapshots / f"{self._counter + 1:03d}_{step_name}.json"
        with self._lock:
            self._counter += 1
            path = self.snapshots / f"{self._counter:03d}_{step_name}.json"
        try:
            path.write_text(
                json.dumps(state.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError):
            return path
        self.record(
            level="DEBUG",
            event="step.state_snapshot",
            message=f"snapshot for {step_name}",
            step=step_name,
            data={"path": str(path)},
        )
        return path

    def close(self) -> None:
        if not self._enabled or self._fp is None:
            return
        try:
            self._fp.close()
        except (OSError, ValueError):
            return


class StepContext:
    def __init__(self, *, run_id: str, step_name: str, attempt: int, session: RunSession | None) -> None:
        self.run_id = run_id
        self.step_name = step_name
        self.attempt = attempt
        self._session = session

    def _emit(self, level: str, event: str, message: str, **data: Any) -> None:
        if self._session is None:
            return
        self._session.record(
            level=level,
            event=event,
            message=message,
            step=self.step_name,
            attempt=self.attempt,
            data=data or None,
        )

    def debug(self, message: str, **data: Any) -> None:
        self._emit("DEBUG", "user.debug", message, **data)

    def info(self, message: str, **data: Any) -> None:
        self._emit("INFO", "user.info", message, **data)

    def warn(self, message: str, **data: Any) -> None:
        self._emit("WARN", "user.warn", message, **data)

    def error(self, message: str, **data: Any) -> None:
        self._emit("ERROR", "user.error", message, **data)
