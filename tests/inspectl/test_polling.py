from __future__ import annotations

import json

import pytest

from inspectl.logging import RunSession, StepContext
from inspectl.polling import PollPolicy, PollTimeout, async_poll_until, poll_until


def test_poll_until_succeeds_after_retries() -> None:
    attempts = {"count": 0}

    def fetch() -> str:
        attempts["count"] += 1
        return "done" if attempts["count"] == 3 else "pending"

    result = poll_until(
        fn=fetch,
        check=lambda value: value == "done",
        policy=PollPolicy(max_attempts=5, interval=0.0, timeout=5.0),
        label="build-123",
    )

    assert result == "done"


def test_poll_until_emits_events_with_ctx(tmp_path) -> None:
    session = RunSession(run_id="run-005", root_dir=tmp_path)
    ctx = StepContext(
        run_id="run-005",
        step_name="poll_build",
        attempt=1,
        session=session,
    )
    attempts = {"count": 0}

    def fetch() -> str:
        attempts["count"] += 1
        return "done" if attempts["count"] == 2 else "pending"

    result = poll_until(
        fn=fetch,
        check=lambda value: value == "done",
        policy=PollPolicy(max_attempts=3, interval=0.0, timeout=5.0),
        label="build-789",
        ctx=ctx,
    )
    session.close()

    assert result == "done"
    payloads = [
        json.loads(line)
        for line in (tmp_path / "run-005" / "session.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(payload["event"] == "poll.attempt" for payload in payloads)
    assert any(payload["event"] == "poll.success" for payload in payloads)


@pytest.mark.asyncio
async def test_async_poll_until_times_out() -> None:
    async def fetch() -> str:
        return "pending"

    with pytest.raises(PollTimeout):
        await async_poll_until(
            fn=fetch,
            check=lambda value: value == "done",
            policy=PollPolicy(max_attempts=2, interval=0.0, timeout=0.1),
            label="build-456",
        )


def test_poll_policy_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        PollPolicy(max_attempts=0, interval=0.0, timeout=1.0)

    with pytest.raises(ValueError, match="interval"):
        PollPolicy(max_attempts=1, interval=-1.0, timeout=1.0)

    with pytest.raises(ValueError, match="timeout"):
        PollPolicy(max_attempts=1, interval=0.0, timeout=-1.0)

    with pytest.raises(ValueError, match="backoff_factor"):
        PollPolicy(max_attempts=1, interval=0.0, timeout=1.0, backoff_factor=0.0)

    with pytest.raises(ValueError, match="max_interval"):
        PollPolicy(max_attempts=1, interval=2.0, timeout=1.0, max_interval=1.0)
