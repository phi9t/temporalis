from __future__ import annotations

from dataclasses import dataclass
import asyncio
import inspect
import time
from typing import Awaitable, Callable, TypeVar

from inspectl.logging import StepContext


ResultT = TypeVar("ResultT")


class PollTimeout(RuntimeError):
    """Raised when polling exhausts attempts or timeout."""


@dataclass(frozen=True)
class PollPolicy:
    max_attempts: int
    interval: float
    timeout: float
    backoff_factor: float = 1.0
    max_interval: float = 60.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0")
        if self.interval < 0:
            raise ValueError("interval must be greater than or equal to 0")
        if self.timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        if self.backoff_factor <= 0:
            raise ValueError("backoff_factor must be greater than 0")
        if self.max_interval <= 0:
            raise ValueError("max_interval must be greater than 0")
        if self.max_interval < self.interval:
            raise ValueError("max_interval must be greater than or equal to interval")


def _emit_poll_event(
    ctx: StepContext | None,
    *,
    level: str,
    event: str,
    message: str,
    label: str,
    attempt: int,
) -> None:
    if ctx is None:
        return
    session = getattr(ctx, "_session", None)
    if session is None:
        return
    try:
        session.record(
            level=level,
            event=event,
            message=message,
            step=ctx.step_name,
            attempt=attempt,
            data={"label": label},
        )
    except (OSError, TypeError, ValueError):
        return


def poll_until(
    *,
    fn: Callable[[], ResultT],
    check: Callable[[ResultT], bool],
    policy: PollPolicy,
    label: str,
    ctx: StepContext | None = None,
) -> ResultT:
    started = time.monotonic()
    delay = policy.interval
    for attempt in range(1, policy.max_attempts + 1):
        _emit_poll_event(
            ctx,
            level="INFO",
            event="poll.attempt",
            message=f"poll attempt {attempt} for {label}",
            label=label,
            attempt=attempt,
        )
        result = fn()
        if check(result):
            _emit_poll_event(
                ctx,
                level="INFO",
                event="poll.success",
                message=f"poll succeeded for {label}",
                label=label,
                attempt=attempt,
            )
            return result
        elapsed = time.monotonic() - started
        remaining = policy.timeout - elapsed
        if remaining <= 0:
            _emit_poll_event(
                ctx,
                level="WARN",
                event="poll.timeout",
                message=f"poll timed out for {label}",
                label=label,
                attempt=attempt,
            )
            raise PollTimeout(f"poll '{label}' timed out after {attempt} attempts")
        if attempt < policy.max_attempts:
            time.sleep(min(delay, remaining))
            delay = min(delay * policy.backoff_factor, policy.max_interval)
    _emit_poll_event(
        ctx,
        level="WARN",
        event="poll.timeout",
        message=f"poll exhausted for {label}",
        label=label,
        attempt=policy.max_attempts,
    )
    raise PollTimeout(f"poll '{label}' exhausted {policy.max_attempts} attempts")


async def async_poll_until(
    *,
    fn: Callable[[], Awaitable[ResultT]] | Callable[[], ResultT],
    check: Callable[[ResultT], bool],
    policy: PollPolicy,
    label: str,
    ctx: StepContext | None = None,
) -> ResultT:
    started = time.monotonic()
    delay = policy.interval
    for attempt in range(1, policy.max_attempts + 1):
        _emit_poll_event(
            ctx,
            level="INFO",
            event="poll.attempt",
            message=f"poll attempt {attempt} for {label}",
            label=label,
            attempt=attempt,
        )
        result = fn()
        if inspect.isawaitable(result):
            result = await result
        if check(result):
            _emit_poll_event(
                ctx,
                level="INFO",
                event="poll.success",
                message=f"poll succeeded for {label}",
                label=label,
                attempt=attempt,
            )
            return result
        elapsed = time.monotonic() - started
        remaining = policy.timeout - elapsed
        if remaining <= 0:
            _emit_poll_event(
                ctx,
                level="WARN",
                event="poll.timeout",
                message=f"poll timed out for {label}",
                label=label,
                attempt=attempt,
            )
            raise PollTimeout(f"poll '{label}' timed out after {attempt} attempts")
        if attempt < policy.max_attempts:
            await asyncio.sleep(min(delay, remaining))
            delay = min(delay * policy.backoff_factor, policy.max_interval)
    _emit_poll_event(
        ctx,
        level="WARN",
        event="poll.timeout",
        message=f"poll exhausted for {label}",
        label=label,
        attempt=policy.max_attempts,
    )
    raise PollTimeout(f"poll '{label}' exhausted {policy.max_attempts} attempts")
