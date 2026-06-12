"""Async subprocess runner that captures output and heartbeats inside activities."""

from __future__ import annotations

import asyncio
from pathlib import Path

from temporalio import activity

TAIL_LINES = 40
HEARTBEAT_EVERY = 20


class SubprocessFailed(RuntimeError):
    """Command exited non-zero; message carries the output tail."""


def _maybe_heartbeat(label: str, line_count: int) -> None:
    try:
        if activity.in_activity():
            activity.heartbeat({"phase": label, "lines": line_count})
    except Exception:
        pass


async def run_logged(cmd: list[str], *, cwd: Path | None = None, label: str) -> list[str]:
    """Run a command, streaming combined output into a list of lines.

    Heartbeats every HEARTBEAT_EVERY lines when called from inside a Temporal
    activity so long docker builds keep the activity alive. Raises
    SubprocessFailed with the last TAIL_LINES lines on non-zero exit.
    """

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    lines: list[str] = []
    assert process.stdout is not None
    _maybe_heartbeat(label, 0)
    async for raw in process.stdout:
        lines.append(raw.decode(errors="replace").rstrip("\n"))
        if len(lines) % HEARTBEAT_EVERY == 0:
            _maybe_heartbeat(label, len(lines))
    code = await process.wait()
    _maybe_heartbeat(label, len(lines))
    if code != 0:
        tail = "\n".join(lines[-TAIL_LINES:])
        raise SubprocessFailed(f"{label}: {' '.join(cmd)} -> exit {code}\n{tail}")
    return lines
