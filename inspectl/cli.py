from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from inspectl.inspection import inspect_run, list_runs, read_run_logs, resume_run
from inspectl.models import RuntimeConfig


def _runtime_config(args: argparse.Namespace) -> RuntimeConfig:
    return RuntimeConfig(
        namespace=args.namespace,
        task_queue_prefix=args.task_queue_prefix,
        local_state_dir=Path(args.local_state_dir),
        log_dir=Path(args.log_dir),
        temporal_cli_path=args.temporal_cli_path,
        host=args.host,
        port=args.port,
    )


def _print_run_table(runs: list[dict[str, Any]]) -> None:
    print("run_id\tstatus\tpipeline\tupdated_at")
    for run in runs:
        print(
            "\t".join(
                str(run.get(column) or "-")
                for column in ("run_id", "status", "pipeline", "updated_at")
            )
        )


def _print_run_details(run: dict[str, Any]) -> None:
    for key in (
        "run_id",
        "status",
        "pipeline",
        "task_queue",
        "failure_step",
        "failure_reason",
        "updated_at",
        "latest_snapshot",
    ):
        value = run.get(key)
        if value is not None:
            print(f"{key}: {value}")


def _print_log_entries(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        parts = [
            str(entry.get("timestamp") or "-"),
            str(entry.get("level") or "-"),
            str(entry.get("event") or "-"),
            str(entry.get("message") or "-"),
        ]
        step = entry.get("step")
        attempt = entry.get("attempt")
        if step is not None:
            parts.append(f"step={step}")
        if attempt is not None:
            parts.append(f"attempt={attempt}")
        data = entry.get("data")
        if data is not None:
            parts.append(f"data={json.dumps(data, sort_keys=True)}")
        print(" ".join(parts))


async def _dispatch(args: argparse.Namespace) -> int:
    config = _runtime_config(args)
    try:
        if args.command == "list":
            _print_run_table(await list_runs(config))
            return 0
        if args.command == "inspect":
            _print_run_details(await inspect_run(args.run_id, config))
            return 0
        if args.command == "logs":
            _print_log_entries(await read_run_logs(args.run_id, config))
            return 0
        if args.command == "resume":
            result = await resume_run(args.run_id, config)
            print(f"{result['run_id']}: {result.get('status', 'unknown')}")
            return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command {args.command!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inspectl")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--task-queue-prefix", default="inspectl")
    parser.add_argument("--local-state-dir", default=".inspectl")
    parser.add_argument("--log-dir", default="runs")
    parser.add_argument("--temporal-cli-path", default="temporal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7233)

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("run_id")

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("run_id")

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("run_id")

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_dispatch(args))
