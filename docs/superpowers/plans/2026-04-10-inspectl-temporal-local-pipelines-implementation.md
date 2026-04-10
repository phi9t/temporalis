# Inspectl Temporal Local Pipelines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `inspectl`, a Python-first local Temporal facade that exposes `@step`, `@pipeline`, `run(...)`, and an `inspectl` CLI while keeping user business logic visually dominant.

**Architecture:** Add a new top-level `inspectl/` package beside `monoctl/`. Durable steps are executed through one dynamic Temporal activity, pipelines run inside one generic workflow class, and `run()` hides local dev-server bootstrap plus ephemeral worker lifecycle. Temporal owns durability and retries; local JSONL logs and state snapshots are derived debugging artifacts.

**Tech Stack:** Python 3.11, Temporal Python SDK, argparse, dataclasses, asyncio, subprocess-managed Temporal CLI dev server, pytest.

---

## File Structure

- Modify: `pyproject.toml`
  Add `temporalio` dependency and the `inspectl` console script while preserving `monoctl`.
- Modify: `.gitignore`
  Ignore local runtime state under `.inspectl/` and generated run artifacts under `runs/`.
- Modify: `README.md`
  Add a short section explaining the new `inspectl` framework and where its docs live.
- Create: `docs/inspectl/README.md`
  Quickstart and maintainer map for the new framework.
- Create: `inspectl/__init__.py`
  Re-export the public API: `PipelineState`, `RetryPolicy`, `StepContext`, `poll_until`, `step`, `pipeline`, and `run`.
- Create: `inspectl/models.py`
  Shared dataclasses for state, retry config, log entries, run descriptions, and local runtime config.
- Create: `inspectl/errors.py`
  Framework-specific exceptions with clear operator-facing messages.
- Create: `inspectl/registry.py`
  Pipeline and step registration, lookup, and duplicate-name checks.
- Create: `inspectl/decorators.py`
  `@step` and `@pipeline` implementations plus the internal dispatch `ContextVar`.
- Create: `inspectl/logging.py`
  JSONL session writing, state snapshot writing, stderr formatting, and `StepContext`.
- Create: `inspectl/polling.py`
  `poll_until` and `async_poll_until` utilities with structured progress logging.
- Create: `inspectl/activity_runtime.py`
  One dynamic activity that resolves a step by name, validates preconditions, injects `StepContext`, and writes snapshots.
- Create: `inspectl/workflow_runtime.py`
  One generic workflow class, resume signal/query handlers, and the durable-step pause loop.
- Create: `inspectl/local_server.py`
  Persistent local Temporal CLI dev-server bootstrap/reuse using `temporal server start-dev --db-filename`.
- Create: `inspectl/runtime.py`
  `run()` and `run_async()` orchestration around local server, client, worker, workflow start/resume, and paused-run detection.
- Create: `inspectl/inspection.py`
  High-level inspection helpers that merge workflow queries with local session files.
- Create: `inspectl/cli.py`
  Operator CLI: `list`, `inspect`, `logs`, and `resume`.
- Create: `tests/inspectl/test_models.py`
  Unit coverage for state serialization and retry-policy mapping.
- Create: `tests/inspectl/test_decorators.py`
  Unit coverage for registration, duplicate names, and direct-call semantics.
- Create: `tests/inspectl/test_logging.py`
  Unit coverage for JSONL logging and state snapshots.
- Create: `tests/inspectl/test_polling.py`
  Unit coverage for sync/async polling behavior.
- Create: `tests/inspectl/test_local_server.py`
  Unit coverage for dev-server command construction and persisted runtime state.
- Create: `tests/inspectl/test_cli.py`
  CLI formatting and command dispatch tests with stubbed inspection services.
- Create: `tests/inspectl/integration/test_run_complete.py`
  End-to-end success path against a real local Temporal environment.
- Create: `tests/inspectl/integration/test_run_pause_resume.py`
  End-to-end paused-workflow and resume path.

### Architectural Notes To Preserve During Implementation

- Durable steps must remain plain Python functions. The framework should route them into Temporal, not rewrite them.
- Workflow code must stay side-effect free. Local JSONL/session writes happen in activities or in the client-side `run()` wrapper, never inside workflow logic.
- Use one generic workflow class plus one dynamic activity. Do not generate workflow/activity classes per pipeline.
- For integration tests, prefer `temporalio.testing.WorkflowEnvironment.start_local(..., dev_server_database_filename=...)` so tests use a real SDK-supported local server without relying on a globally installed CLI.
- For production/local-first execution, bootstrap a persistent Temporal CLI dev server with `temporal server start-dev --db-filename <sqlite-file> --headless`.

### Task 1: Add Packaging, Core Models, And Error Types

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `inspectl/__init__.py`
- Create: `inspectl/models.py`
- Create: `inspectl/errors.py`
- Test: `tests/inspectl/test_models.py`

- [ ] **Step 1: Create the new package and test directories**

Run:

```bash
mkdir -p inspectl
mkdir -p tests/inspectl
mkdir -p tests/inspectl/integration
mkdir -p docs/inspectl
```

Expected: the four directories exist with no output.

- [ ] **Step 2: Write the failing model tests**

Create `tests/inspectl/test_models.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from temporalio.common import RetryPolicy as TemporalRetryPolicy

from inspectl.models import PipelineState, RetryPolicy


class PipelineMode(str, Enum):
    COMMIT_FIRST = "commit-first"


@dataclass
class ExampleState(PipelineState):
    pipeline_mode: PipelineMode | None = None
    build_id: str | None = None


def test_pipeline_state_to_dict_serializes_enums() -> None:
    state = ExampleState(
        run_id="run-001",
        status="running",
        pipeline_mode=PipelineMode.COMMIT_FIRST,
        build_id="build-123",
    )

    payload = state.to_dict()

    assert payload["run_id"] == "run-001"
    assert payload["pipeline_mode"] == "commit-first"
    assert payload["build_id"] == "build-123"


def test_pipeline_state_from_dict_round_trips() -> None:
    restored = ExampleState.from_dict(
        {
            "run_id": "run-002",
            "status": "paused",
            "failure_step": "submit_compilation",
            "pipeline_mode": "commit-first",
            "build_id": "build-456",
        }
    )

    assert restored.run_id == "run-002"
    assert restored.status == "paused"
    assert restored.failure_step == "submit_compilation"
    assert restored.pipeline_mode is PipelineMode.COMMIT_FIRST
    assert restored.build_id == "build-456"


def test_retry_policy_maps_to_temporal_policy() -> None:
    policy = RetryPolicy(max_attempts=3, backoff=2.0, max_interval_seconds=45)

    temporal_policy = policy.to_temporal_retry_policy()

    assert isinstance(temporal_policy, TemporalRetryPolicy)
    assert temporal_policy.maximum_attempts == 3
    assert temporal_policy.backoff_coefficient == 2.0
    assert temporal_policy.maximum_interval.total_seconds() == 45
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
pytest -q tests/inspectl/test_models.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'inspectl'`.

- [ ] **Step 4: Add package metadata and ignore runtime output**

Modify `pyproject.toml` so the project stanza reads:

```toml
[project]
name = "monoctl"
version = "0.1.0"
description = "Workspace control plane for the temporalis repo constellation"
requires-python = ">=3.11"
dependencies = [
  "PyYAML>=6.0",
  "temporalio>=1.9,<2",
]

[project.scripts]
monoctl = "monoctl.cli:run"
inspectl = "inspectl.cli:run"
```

Modify `.gitignore` by appending:

```gitignore
.inspectl/
runs/
```

- [ ] **Step 5: Implement the core models and errors**

Create `inspectl/models.py` with:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Mapping, TypeVar

from temporalio.common import RetryPolicy as TemporalRetryPolicy


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {k: _serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value


StateT = TypeVar("StateT", bound="PipelineState")


@dataclass
class PipelineState:
    run_id: str
    status: str = "pending"
    failure_step: str | None = None
    failure_reason: str | None = None
    started_at: str | None = None
    updated_at: str | None = None

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {}

    def to_dict(self) -> dict[str, Any]:
        return {field.name: _serialize(getattr(self, field.name)) for field in fields(self)}

    @classmethod
    def from_dict(cls: type[StateT], data: Mapping[str, Any]) -> StateT:
        kwargs: dict[str, Any] = {}
        for field in fields(cls):
            if field.name not in data:
                continue
            value = data[field.name]
            enum_type = getattr(cls, "_enum_fields", {}).get(field.name)
            if enum_type and value is not None:
                kwargs[field.name] = enum_type(value)
            else:
                kwargs[field.name] = value
        return cls(**kwargs)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff: float = 1.0
    max_interval_seconds: int = 300

    def to_temporal_retry_policy(self) -> TemporalRetryPolicy:
        return TemporalRetryPolicy(
            maximum_attempts=self.max_attempts,
            backoff_coefficient=self.backoff,
            maximum_interval=timedelta(seconds=self.max_interval_seconds),
        )


@dataclass(frozen=True)
class RuntimeConfig:
    namespace: str = "default"
    task_queue_prefix: str = "inspectl"
    local_state_dir: Path = Path(".inspectl")
    log_dir: Path = Path("runs")
    temporal_cli_path: str = "temporal"
    host: str = "127.0.0.1"
    port: int = 7233
```

Create `inspectl/errors.py` with:

```python
class InspectlError(RuntimeError):
    """Base exception for inspectl."""


class StepDefinitionError(InspectlError):
    """Raised when a step definition is invalid."""


class PipelineDefinitionError(InspectlError):
    """Raised when a pipeline definition is invalid."""


class DuplicateStepNameError(InspectlError):
    """Raised when two steps share the same effective name."""


class StepPreconditionError(InspectlError):
    """Raised when a step's declared requirements are not satisfied."""


class StepExecutionError(InspectlError):
    """Raised when a step returns an invalid value or cannot execute."""


class PipelinePaused(InspectlError):
    """Raised by run() when the underlying workflow is paused awaiting resume."""
```

Create `inspectl/__init__.py` with:

```python
from inspectl.models import PipelineState, RetryPolicy

__all__ = [
    "PipelineState",
    "RetryPolicy",
]
```

- [ ] **Step 6: Run the model tests to verify they pass**

Run:

```bash
pytest -q tests/inspectl/test_models.py
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore inspectl/__init__.py inspectl/models.py inspectl/errors.py tests/inspectl/test_models.py
git commit -m "feat: add inspectl core models"
```

### Task 2: Add The Registry And Decorator Surface

**Files:**
- Modify: `inspectl/__init__.py`
- Create: `inspectl/registry.py`
- Create: `inspectl/decorators.py`
- Test: `tests/inspectl/test_decorators.py`

- [ ] **Step 1: Write the failing decorator tests**

Create `tests/inspectl/test_decorators.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

import pytest

from inspectl.decorators import pipeline, step
from inspectl.errors import DuplicateStepNameError, PipelineDefinitionError
from inspectl.models import PipelineState


@dataclass
class ExampleState(PipelineState):
    value: int = 0


def test_step_runs_directly_outside_workflow() -> None:
    @step()
    def increment(state: ExampleState) -> ExampleState:
        state.value += 1
        return state

    result = increment(ExampleState(run_id="run-001"))

    assert result.value == 1


def test_duplicate_step_names_raise() -> None:
    @step(name="shared")
    def first(state: ExampleState) -> ExampleState:
        return state

    with pytest.raises(DuplicateStepNameError):
        @step(name="shared")
        def second(state: ExampleState) -> ExampleState:
            return state


def test_pipeline_must_be_async() -> None:
    with pytest.raises(PipelineDefinitionError):
        @pipeline(name="bad-pipeline")
        def not_async(state: ExampleState) -> ExampleState:
            return state
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest -q tests/inspectl/test_decorators.py
```

Expected: FAIL because `inspectl.decorators` does not exist.

- [ ] **Step 3: Implement the registry**

Create `inspectl/registry.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from inspectl.errors import DuplicateStepNameError
from inspectl.models import RetryPolicy


StateFn = Callable[..., Any]


@dataclass(frozen=True)
class StepDefinition:
    name: str
    fn: StateFn
    retry_policy: RetryPolicy
    transient: bool
    requires: tuple[str, ...]
    produces: tuple[str, ...]


@dataclass(frozen=True)
class PipelineDefinition:
    name: str
    fn: Callable[..., Awaitable[Any]]
    owner: str | None
    description: str | None


_STEPS: dict[str, StepDefinition] = {}
_PIPELINES: dict[str, PipelineDefinition] = {}


def clear_registry() -> None:
    _STEPS.clear()
    _PIPELINES.clear()


def register_step(definition: StepDefinition) -> StepDefinition:
    existing = _STEPS.get(definition.name)
    if existing and existing.fn is not definition.fn:
        raise DuplicateStepNameError(
            f"steps '{existing.fn.__module__}.{existing.fn.__name__}' and "
            f"'{definition.fn.__module__}.{definition.fn.__name__}' share name '{definition.name}'"
        )
    _STEPS[definition.name] = definition
    return definition


def register_pipeline(definition: PipelineDefinition) -> PipelineDefinition:
    _PIPELINES[definition.name] = definition
    return definition


def get_step(name: str) -> StepDefinition:
    return _STEPS[name]


def get_pipeline(name: str) -> PipelineDefinition:
    return _PIPELINES[name]
```

- [ ] **Step 4: Implement the decorators**

Create `inspectl/decorators.py` with:

```python
from __future__ import annotations

import inspect
from contextvars import ContextVar
from functools import wraps
from typing import Any, Protocol

from inspectl.errors import PipelineDefinitionError
from inspectl.models import RetryPolicy
from inspectl.registry import PipelineDefinition, StepDefinition, register_pipeline, register_step


class StepDispatcher(Protocol):
    def call_step(self, definition: StepDefinition, state: Any) -> Any:
        ...


_DISPATCHER: ContextVar[StepDispatcher | None] = ContextVar("inspectl_dispatcher", default=None)


def current_dispatcher() -> StepDispatcher | None:
    return _DISPATCHER.get()


def set_dispatcher(dispatcher: StepDispatcher | None):
    return _DISPATCHER.set(dispatcher)


def reset_dispatcher(token: object) -> None:
    _DISPATCHER.reset(token)


def step(
    *,
    max_attempts: int = 1,
    backoff: float = 1.0,
    transient: bool = False,
    requires: list[str] | tuple[str, ...] = (),
    produces: list[str] | tuple[str, ...] = (),
    name: str | None = None,
):
    def decorate(fn):
        definition = register_step(
            StepDefinition(
                name=name or fn.__name__,
                fn=fn,
                retry_policy=RetryPolicy(max_attempts=max_attempts, backoff=backoff),
                transient=transient,
                requires=tuple(requires),
                produces=tuple(produces),
            )
        )

        @wraps(fn)
        def wrapper(state, *args, **kwargs):
            dispatcher = current_dispatcher()
            if dispatcher is None:
                return fn(state, *args, **kwargs)
            if definition.transient:
                return fn(state, *args, **kwargs)
            return dispatcher.call_step(definition, state)

        wrapper._inspectl_step = definition
        return wrapper

    return decorate


def pipeline(*, name: str, owner: str | None = None, description: str | None = None):
    def decorate(fn):
        if not inspect.iscoroutinefunction(fn):
            raise PipelineDefinitionError(f"pipeline '{name}' must be defined with async def")

        register_pipeline(PipelineDefinition(name=name, fn=fn, owner=owner, description=description))

        @wraps(fn)
        async def wrapper(state, *args, **kwargs):
            return await fn(state, *args, **kwargs)

        wrapper._inspectl_pipeline_name = name
        return wrapper

    return decorate
```

Modify `inspectl/__init__.py` to:

```python
from inspectl.decorators import pipeline, step
from inspectl.models import PipelineState, RetryPolicy

__all__ = [
    "PipelineState",
    "RetryPolicy",
    "pipeline",
    "step",
]
```

- [ ] **Step 5: Run the decorator tests**

Run:

```bash
pytest -q tests/inspectl/test_decorators.py
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add inspectl/__init__.py inspectl/registry.py inspectl/decorators.py tests/inspectl/test_decorators.py
git commit -m "feat: add inspectl registration and decorators"
```

### Task 3: Add Session Logging, StepContext, And Polling Helpers

**Files:**
- Modify: `inspectl/__init__.py`
- Create: `inspectl/logging.py`
- Create: `inspectl/polling.py`
- Test: `tests/inspectl/test_logging.py`
- Test: `tests/inspectl/test_polling.py`

- [ ] **Step 1: Write the failing logging tests**

Create `tests/inspectl/test_logging.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
import json

from inspectl.logging import RunSession, StepContext
from inspectl.models import PipelineState


@dataclass
class ExampleState(PipelineState):
    build_id: str | None = None


def test_run_session_writes_jsonl_and_snapshot(tmp_path) -> None:
    session = RunSession(run_id="run-001", root_dir=tmp_path)
    session.record(level="INFO", event="run.start", message="starting")
    session.snapshot(step_name="submit_compilation", state=ExampleState(run_id="run-001", build_id="build-123"))
    session.close()

    entries = [json.loads(line) for line in (tmp_path / "run-001" / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    snapshot = json.loads((tmp_path / "run-001" / "state_snapshots" / "001_submit_compilation.json").read_text(encoding="utf-8"))

    assert entries[0]["event"] == "run.start"
    assert snapshot["build_id"] == "build-123"


def test_step_context_scopes_user_logs(tmp_path) -> None:
    session = RunSession(run_id="run-002", root_dir=tmp_path)
    ctx = StepContext(run_id="run-002", step_name="submit_compilation", attempt=2, session=session)

    ctx.info("submitted", build_id="build-456")
    session.close()

    payload = json.loads((tmp_path / "run-002" / "session.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "user.info"
    assert payload["step"] == "submit_compilation"
    assert payload["attempt"] == 2
    assert payload["data"]["build_id"] == "build-456"
```

- [ ] **Step 2: Write the failing polling tests**

Create `tests/inspectl/test_polling.py` with:

```python
from __future__ import annotations

import asyncio

import pytest

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
```

- [ ] **Step 3: Run the logging and polling tests to verify they fail**

Run:

```bash
pytest -q tests/inspectl/test_logging.py tests/inspectl/test_polling.py
```

Expected: FAIL because `inspectl.logging` and `inspectl.polling` do not exist.

- [ ] **Step 4: Implement session logging and StepContext**

Create `inspectl/logging.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
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
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._counter = 0
        self._fp = (self.root / "session.jsonl").open("a", encoding="utf-8", buffering=1)

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
        with self._lock:
            self._fp.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def snapshot(self, *, step_name: str, state: PipelineState) -> Path:
        self._counter += 1
        path = self.snapshots / f"{self._counter:03d}_{step_name}.json"
        path.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        self.record(
            level="DEBUG",
            event="step.state_snapshot",
            message=f"snapshot for {step_name}",
            step=step_name,
            data={"path": str(path)},
        )
        return path

    def close(self) -> None:
        self._fp.close()


class StepContext:
    def __init__(self, *, run_id: str, step_name: str, attempt: int, session: RunSession | None) -> None:
        self.run_id = run_id
        self.step_name = step_name
        self.attempt = attempt
        self._session = session

    def _emit(self, level: str, event: str, message: str, **data: Any) -> None:
        if self._session:
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
```

- [ ] **Step 5: Implement polling**

Create `inspectl/polling.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import time
from typing import Awaitable, Callable, TypeVar


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


def poll_until(
    *,
    fn: Callable[[], ResultT],
    check: Callable[[ResultT], bool],
    policy: PollPolicy,
    label: str,
) -> ResultT:
    started = time.monotonic()
    delay = policy.interval
    for attempt in range(1, policy.max_attempts + 1):
        result = fn()
        if check(result):
            return result
        if time.monotonic() - started >= policy.timeout:
            raise PollTimeout(f"poll '{label}' timed out after {attempt} attempts")
        time.sleep(delay)
        delay = min(delay * policy.backoff_factor, policy.max_interval)
    raise PollTimeout(f"poll '{label}' exhausted {policy.max_attempts} attempts")


async def async_poll_until(
    *,
    fn: Callable[[], Awaitable[ResultT]] | Callable[[], ResultT],
    check: Callable[[ResultT], bool],
    policy: PollPolicy,
    label: str,
) -> ResultT:
    started = time.monotonic()
    delay = policy.interval
    for attempt in range(1, policy.max_attempts + 1):
        result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
        if check(result):
            return result
        if time.monotonic() - started >= policy.timeout:
            raise PollTimeout(f"poll '{label}' timed out after {attempt} attempts")
        await asyncio.sleep(delay)
        delay = min(delay * policy.backoff_factor, policy.max_interval)
    raise PollTimeout(f"poll '{label}' exhausted {policy.max_attempts} attempts")
```

Modify `inspectl/__init__.py` to:

```python
from inspectl.decorators import pipeline, step
from inspectl.logging import StepContext
from inspectl.models import PipelineState, RetryPolicy
from inspectl.polling import PollPolicy, async_poll_until, poll_until

__all__ = [
    "PipelineState",
    "PollPolicy",
    "RetryPolicy",
    "StepContext",
    "async_poll_until",
    "pipeline",
    "poll_until",
    "step",
]
```

- [ ] **Step 6: Run the logging and polling tests**

Run:

```bash
pytest -q tests/inspectl/test_logging.py tests/inspectl/test_polling.py
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add inspectl/__init__.py inspectl/logging.py inspectl/polling.py tests/inspectl/test_logging.py tests/inspectl/test_polling.py
git commit -m "feat: add inspectl logging and polling helpers"
```

### Task 4: Implement The Generic Workflow And Dynamic Activity Dispatcher

**Files:**
- Modify: `inspectl/decorators.py`
- Create: `inspectl/activity_runtime.py`
- Create: `inspectl/workflow_runtime.py`
- Test: `tests/inspectl/integration/test_run_complete.py`

- [ ] **Step 1: Write the failing end-to-end success test**

Create `tests/inspectl/integration/test_run_complete.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from inspectl import PipelineState, pipeline, step
from inspectl.activity_runtime import inspectl_step_activity
from inspectl.workflow_runtime import InspectlPipelineWorkflow


@dataclass
class ExampleState(PipelineState):
    build_id: str | None = None


@step(produces=["build_id"])
def submit_compilation(state: ExampleState) -> ExampleState:
    state.build_id = "build-123"
    return state


@pipeline(name="demo-pipeline")
async def demo_pipeline(state: ExampleState) -> ExampleState:
    state = await submit_compilation(state)
    return state


@pytest.mark.asyncio
async def test_generic_workflow_executes_step_activity(tmp_path: Path) -> None:
    async with await WorkflowEnvironment.start_local(
        dev_server_database_filename=str(tmp_path / "temporal.sqlite"),
    ) as env:
        worker = Worker(
            env.client,
            task_queue="inspectl-demo",
            workflows=[InspectlPipelineWorkflow],
            activities=[inspectl_step_activity],
        )
        async with worker:
            result = await env.client.execute_workflow(
                InspectlPipelineWorkflow.run,
                {
                    "pipeline_name": "demo-pipeline",
                    "state": ExampleState(run_id="run-001").to_dict(),
                    "log_dir": str(tmp_path / "runs"),
                },
                id="run-001",
                task_queue="inspectl-demo",
            )

    restored = ExampleState.from_dict(result)
    assert restored.build_id == "build-123"
    assert (tmp_path / "runs" / "run-001" / "state_snapshots" / "001_submit_compilation.json").exists()
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run:

```bash
pytest -q tests/inspectl/integration/test_run_complete.py -k generic_workflow
```

Expected: FAIL because `inspectl.activity_runtime` and `inspectl.workflow_runtime` do not exist.

- [ ] **Step 3: Implement the dynamic activity**

Create `inspectl/activity_runtime.py` with:

```python
from __future__ import annotations

from inspect import iscoroutinefunction, signature
import json
from pathlib import Path
from typing import Sequence

from temporalio import activity
from temporalio.common import RawValue

from inspectl.errors import StepExecutionError, StepPreconditionError
from inspectl.logging import RunSession, StepContext
from inspectl.registry import get_step


def _decode_input(args: Sequence[RawValue]) -> dict:
    return activity.payload_converter().from_payload(args[0].payload, dict)


@activity.defn(dynamic=True)
async def inspectl_step_activity(args: Sequence[RawValue]) -> dict:
    payload = _decode_input(args)
    definition = get_step(activity.info().activity_type)
    state_type = definition.fn.__annotations__.get("state")
    state = state_type.from_dict(payload["state"])

    for field_name in definition.requires:
        if getattr(state, field_name, None) is None:
            raise StepPreconditionError(
                f"step '{definition.name}' requires '{field_name}' but it is None"
            )

    session = RunSession(run_id=state.run_id, root_dir=Path(payload["log_dir"]))
    session.record(level="INFO", event="step.start", message=f"starting {definition.name}", step=definition.name)
    ctx = StepContext(
        run_id=state.run_id,
        step_name=definition.name,
        attempt=activity.info().attempt,
        session=session,
    )

    params = list(signature(definition.fn).parameters.values())
    if len(params) >= 2:
        result = await definition.fn(state, ctx) if iscoroutinefunction(definition.fn) else definition.fn(state, ctx)
    else:
        result = await definition.fn(state) if iscoroutinefunction(definition.fn) else definition.fn(state)

    if result is None or not hasattr(result, "to_dict"):
        raise StepExecutionError(f"step '{definition.name}' returned invalid state")

    session.record(level="INFO", event="step.success", message=f"completed {definition.name}", step=definition.name)
    session.snapshot(step_name=definition.name, state=result)
    session.close()
    return result.to_dict()
```

- [ ] **Step 4: Implement the workflow runtime and durable-step pause loop**

Create `inspectl/workflow_runtime.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

from inspectl.decorators import reset_dispatcher, set_dispatcher
from inspectl.models import RuntimeConfig
from inspectl.registry import get_pipeline, StepDefinition


@dataclass
class DispatchState:
    state: dict
    status: str = "running"
    failure_step: str | None = None
    failure_reason: str | None = None
    resume_requested: bool = False


class WorkflowStepDispatcher:
    def __init__(self, runtime: "InspectlPipelineWorkflow", log_dir: str) -> None:
        self.runtime = runtime
        self.log_dir = log_dir

    async def call_step(self, definition: StepDefinition, state):
        while True:
            try:
                payload = {
                    "state": state.to_dict(),
                    "log_dir": self.log_dir,
                }
                result = await workflow.execute_activity(
                    definition.name,
                    payload,
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=definition.retry_policy.to_temporal_retry_policy(),
                )
                restored = type(state).from_dict(result)
                self.runtime._dispatch.status = "running"
                self.runtime._dispatch.failure_step = None
                self.runtime._dispatch.failure_reason = None
                self.runtime._dispatch.state = restored.to_dict()
                return restored
            except Exception as exc:
                self.runtime._dispatch.status = "paused"
                self.runtime._dispatch.failure_step = definition.name
                self.runtime._dispatch.failure_reason = str(exc)
                await workflow.wait_condition(lambda: self.runtime._dispatch.resume_requested)
                self.runtime._dispatch.resume_requested = False


@workflow.defn
class InspectlPipelineWorkflow:
    def __init__(self) -> None:
        self._dispatch = DispatchState(state={})

    @workflow.signal
    def resume(self) -> None:
        self._dispatch.resume_requested = True

    @workflow.query
    def describe(self) -> dict:
        return {
            "status": self._dispatch.status,
            "failure_step": self._dispatch.failure_step,
            "failure_reason": self._dispatch.failure_reason,
            "state": self._dispatch.state,
        }

    @workflow.run
    async def run(self, payload: dict) -> dict:
        pipeline = get_pipeline(payload["pipeline_name"])
        state_type = pipeline.fn.__annotations__["state"]
        state = state_type.from_dict(payload["state"])
        self._dispatch.state = state.to_dict()
        dispatcher = WorkflowStepDispatcher(self, payload["log_dir"])
        token = set_dispatcher(dispatcher)
        try:
            result = await pipeline.fn(state)
            self._dispatch.state = result.to_dict()
            self._dispatch.status = "completed"
            return result.to_dict()
        finally:
            reset_dispatcher(token)
```

- [ ] **Step 5: Run the success integration test**

Run:

```bash
pytest -q tests/inspectl/integration/test_run_complete.py -k generic_workflow
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add inspectl/activity_runtime.py inspectl/workflow_runtime.py inspectl/decorators.py tests/inspectl/integration/test_run_complete.py
git commit -m "feat: add inspectl workflow and activity runtime"
```

### Task 5: Add Persistent Local Dev-Server Bootstrap And `run()`

**Files:**
- Create: `inspectl/local_server.py`
- Create: `inspectl/runtime.py`
- Test: `tests/inspectl/test_local_server.py`
- Test: `tests/inspectl/integration/test_run_pause_resume.py`

- [ ] **Step 1: Write the failing local-server unit tests**

Create `tests/inspectl/test_local_server.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from inspectl.local_server import LocalServerManager
from inspectl.models import RuntimeConfig


def test_local_server_builds_temporal_start_dev_command(tmp_path: Path) -> None:
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl")
    manager = LocalServerManager(config)

    command = manager.build_command(port=7233)

    assert command[:3] == ["temporal", "server", "start-dev"]
    assert "--db-filename" in command
    assert "--headless" in command


@patch("inspectl.local_server.subprocess.Popen")
def test_local_server_persists_runtime_metadata(popen: Mock, tmp_path: Path) -> None:
    popen.return_value.pid = 4242
    config = RuntimeConfig(local_state_dir=tmp_path / ".inspectl")
    manager = LocalServerManager(config)

    manager.write_state(pid=4242, target="127.0.0.1:7233")

    payload = json.loads((tmp_path / ".inspectl" / "runtime" / "server.json").read_text(encoding="utf-8"))
    assert payload["pid"] == 4242
    assert payload["target"] == "127.0.0.1:7233"
```

- [ ] **Step 2: Write the failing pause/resume integration test**

Create `tests/inspectl/integration/test_run_pause_resume.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from temporalio.testing import WorkflowEnvironment

from inspectl import PipelineState, pipeline, step
from inspectl.errors import PipelinePaused
from inspectl.runtime import run_async


@dataclass
class ExampleState(PipelineState):
    attempts: int = 0
    done: bool = False


GATE = {"open": False}


@step(max_attempts=1)
def flaky_step(state: ExampleState) -> ExampleState:
    state.attempts += 1
    if not GATE["open"]:
        raise RuntimeError("still blocked")
    state.done = True
    return state


@pipeline(name="pause-pipeline")
async def pause_pipeline(state: ExampleState) -> ExampleState:
    state = await flaky_step(state)
    return state


@pytest.mark.asyncio
async def test_run_async_pauses_and_resumes(tmp_path: Path) -> None:
    async with await WorkflowEnvironment.start_local(
        dev_server_database_filename=str(tmp_path / "temporal.sqlite"),
    ) as env:
        with pytest.raises(PipelinePaused):
            await run_async(
                pause_pipeline,
                ExampleState(run_id="run-001"),
                client=env.client,
                log_dir=tmp_path / "runs",
            )

        GATE["open"] = True
        result = await run_async(
            pause_pipeline,
            ExampleState(run_id="run-001"),
            client=env.client,
            resume=True,
            log_dir=tmp_path / "runs",
        )

    assert result.done is True
    assert result.attempts == 2
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
pytest -q tests/inspectl/test_local_server.py tests/inspectl/integration/test_run_pause_resume.py
```

Expected: FAIL because `inspectl.local_server` and `inspectl.runtime` do not exist.

- [ ] **Step 4: Implement the local server manager**

Create `inspectl/local_server.py` with:

```python
from __future__ import annotations

import json
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
        self.state_file.write_text(json.dumps({"pid": pid, "target": target}, indent=2), encoding="utf-8")

    def read_state(self) -> dict[str, Any] | None:
        if not self.state_file.exists():
            return None
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def start(self) -> dict[str, Any]:
        process = subprocess.Popen(
            self.build_command(port=self.config.port),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        target = f"{self.config.host}:{self.config.port}"
        self.write_state(pid=process.pid, target=target)
        return {"pid": process.pid, "target": target}
```

- [ ] **Step 5: Implement `run_async()` and `run()`**

Create `inspectl/runtime.py` with:

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from temporalio.client import Client, WorkflowIDReusePolicy
from temporalio.worker import Worker

from inspectl.errors import PipelinePaused
from inspectl.local_server import LocalServerManager
from inspectl.logging import RunSession
from inspectl.models import RuntimeConfig
from inspectl.workflow_runtime import InspectlPipelineWorkflow
from inspectl.activity_runtime import inspectl_step_activity


async def _query_until_terminal(handle) -> dict | None:
    while True:
        description = await handle.query(InspectlPipelineWorkflow.describe)
        if description["status"] == "paused":
            return description
        await asyncio.sleep(0.2)


async def run_async(
    pipeline_fn,
    state,
    *,
    client: Client | None = None,
    resume: bool = True,
    log_dir: Path | str = Path("runs"),
    config: RuntimeConfig | None = None,
):
    config = config or RuntimeConfig()
    session = RunSession(run_id=state.run_id, root_dir=Path(log_dir))
    owns_client = client is None
    if client is None:
        server = LocalServerManager(config)
        details = server.read_state() or server.start()
        client = await Client.connect(details["target"], namespace=config.namespace)

    task_queue = f"{config.task_queue_prefix}-{getattr(pipeline_fn, '_inspectl_pipeline_name')}"
    worker = Worker(client, task_queue=task_queue, workflows=[InspectlPipelineWorkflow], activities=[inspectl_step_activity])
    async with worker:
        handle = client.get_workflow_handle(state.run_id)
        try:
            if resume:
                await handle.signal(InspectlPipelineWorkflow.resume)
            else:
                raise RuntimeError("force new run")
        except Exception:
            handle = await client.start_workflow(
                InspectlPipelineWorkflow.run,
                {
                    "pipeline_name": pipeline_fn._inspectl_pipeline_name,
                    "state": state.to_dict(),
                    "log_dir": str(log_dir),
                },
                id=state.run_id,
                task_queue=task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.WORKFLOW_ID_REUSE_POLICY_REJECT_DUPLICATE,
            )

        session.record(level="INFO", event="run.start", message="workflow started", data={"pipeline": pipeline_fn._inspectl_pipeline_name})
        result_task = asyncio.create_task(handle.result())
        paused_task = asyncio.create_task(_query_until_terminal(handle))
        done, pending = await asyncio.wait({result_task, paused_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if paused_task in done and paused_task.result():
            description = paused_task.result()
            session.record(level="ERROR", event="run.paused", message="workflow paused", data=description)
            session.close()
            raise PipelinePaused(description["failure_reason"] or "workflow paused")
        result = result_task.result()
        session.record(level="INFO", event="run.complete", message="workflow completed")
        session.close()
        return type(state).from_dict(result)


def run(pipeline_fn, state, **kwargs):
    return asyncio.run(run_async(pipeline_fn, state, **kwargs))
```

- [ ] **Step 6: Run the unit and integration tests**

Run:

```bash
pytest -q tests/inspectl/test_local_server.py tests/inspectl/integration/test_run_pause_resume.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add inspectl/local_server.py inspectl/runtime.py tests/inspectl/test_local_server.py tests/inspectl/integration/test_run_pause_resume.py
git commit -m "feat: add inspectl local runtime and resume flow"
```

### Task 6: Build Inspection Helpers And The `inspectl` CLI

**Files:**
- Create: `inspectl/inspection.py`
- Create: `inspectl/cli.py`
- Test: `tests/inspectl/test_cli.py`
- Modify: `inspectl/__init__.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/inspectl/test_cli.py` with:

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from inspectl.cli import main


def test_list_command_renders_runs(tmp_path: Path, capsys, monkeypatch) -> None:
    async def fake_list_runs(*, runtime_dir: Path):
        return [
            {"run_id": "run-003", "status": "running", "pipeline": "demo-pipeline"},
        ]

    monkeypatch.setattr("inspectl.cli.list_runs", fake_list_runs)

    exit_code = main(["list", "--runtime-dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "run-003" in captured.out
    assert "running" in captured.out


def test_inspect_command_renders_run_summary(tmp_path: Path, capsys, monkeypatch) -> None:
    async def fake_inspect(run_id: str, *, runtime_dir: Path):
        return {
            "run_id": run_id,
            "status": "paused",
            "pipeline": "demo-pipeline",
            "failure_step": "submit_compilation",
            "failure_reason": "timeout",
        }

    monkeypatch.setattr("inspectl.cli.inspect_run", fake_inspect)

    exit_code = main(["inspect", "run-001", "--runtime-dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "run-001" in captured.out
    assert "submit_compilation" in captured.out


def test_logs_command_prints_session_jsonl(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "runs" / "run-002"
    run_dir.mkdir(parents=True)
    (run_dir / "session.jsonl").write_text('{"event":"run.start"}\n{"event":"run.complete"}\n', encoding="utf-8")

    exit_code = main(["logs", "run-002", "--log-dir", str(tmp_path / "runs")])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "run.start" in captured.out
    assert "run.complete" in captured.out


def test_resume_command_signals_workflow(tmp_path: Path, capsys, monkeypatch) -> None:
    called: dict[str, str] = {}

    async def fake_resume(run_id: str, *, runtime_dir: Path) -> None:
        called["run_id"] = run_id

    monkeypatch.setattr("inspectl.cli.resume_run", fake_resume)

    exit_code = main(["resume", "run-004", "--runtime-dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert called["run_id"] == "run-004"
    assert "resume signal sent" in captured.out.lower()
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run:

```bash
pytest -q tests/inspectl/test_cli.py
```

Expected: FAIL because `inspectl.cli` does not exist.

- [ ] **Step 3: Implement inspection helpers**

Create `inspectl/inspection.py` with:

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from temporalio.client import Client

from inspectl.local_server import LocalServerManager
from inspectl.models import RuntimeConfig
from inspectl.workflow_runtime import InspectlPipelineWorkflow


async def _connect(runtime_dir: Path) -> Client:
    config = RuntimeConfig(local_state_dir=runtime_dir)
    manager = LocalServerManager(config)
    state = manager.read_state()
    if not state:
        raise RuntimeError("inspectl local server is not running")
    return await Client.connect(state["target"], namespace=config.namespace)


async def list_runs(*, runtime_dir: Path) -> list[dict]:
    client = await _connect(runtime_dir)
    runs: list[dict] = []
    async for execution in client.list_workflows("WorkflowType = 'InspectlPipelineWorkflow'"):
        runs.append(
            {
                "run_id": execution.id,
                "status": execution.status.name.lower(),
                "pipeline": execution.type,
            }
        )
    return runs


async def inspect_run(run_id: str, *, runtime_dir: Path) -> dict:
    client = await _connect(runtime_dir)
    handle = client.get_workflow_handle(run_id)
    description = await handle.query(InspectlPipelineWorkflow.describe)
    run_root = runtime_dir / run_id
    session_path = run_root / "session.jsonl"
    latest_snapshot = None
    snapshots = sorted((run_root / "state_snapshots").glob("*.json")) if (run_root / "state_snapshots").exists() else []
    if snapshots:
        latest_snapshot = json.loads(snapshots[-1].read_text(encoding="utf-8"))

    failure_step = None
    failure_reason = None
    if session_path.exists():
        for line in session_path.read_text(encoding="utf-8").splitlines():
            payload = json.loads(line)
            if payload["event"] == "run.paused":
                failure_step = payload["data"].get("failure_step")
                failure_reason = payload["data"].get("failure_reason")

    return {
        "run_id": run_id,
        "status": description["status"],
        "pipeline": latest_snapshot.get("pipeline_name") if latest_snapshot else None,
        "failure_step": failure_step or description.get("failure_step"),
        "failure_reason": failure_reason or description.get("failure_reason"),
        "latest_snapshot": latest_snapshot,
    }


def read_logs(run_id: str, *, log_dir: Path) -> list[str]:
    session_path = log_dir / run_id / "session.jsonl"
    if not session_path.exists():
        return []
    return session_path.read_text(encoding="utf-8").splitlines()


async def resume_run(run_id: str, *, runtime_dir: Path) -> None:
    client = await _connect(runtime_dir)
    handle = client.get_workflow_handle(run_id)
    await handle.signal(InspectlPipelineWorkflow.resume)
```

- [ ] **Step 4: Implement the CLI**

Create `inspectl/cli.py` with:

```python
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from inspectl.inspection import inspect_run, list_runs, read_logs, resume_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inspectl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--runtime-dir", type=Path, default=Path(".inspectl"))

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("run_id")
    inspect_parser.add_argument("--runtime-dir", type=Path, default=Path(".inspectl"))

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("run_id")
    logs_parser.add_argument("--log-dir", type=Path, default=Path("runs"))

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("run_id")
    resume_parser.add_argument("--runtime-dir", type=Path, default=Path(".inspectl"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        for run in asyncio.run(list_runs(runtime_dir=args.runtime_dir)):
            print(f"{run['run_id']}\t{run['status']}\t{run['pipeline']}")
        return 0

    if args.command == "inspect":
        result = asyncio.run(inspect_run(args.run_id, runtime_dir=args.runtime_dir))
        print(f"Run: {result['run_id']}")
        print(f"Status: {result['status']}")
        if result["failure_step"]:
            print(f"Failed at: {result['failure_step']}")
        if result["failure_reason"]:
            print(f"Reason: {result['failure_reason']}")
        return 0

    if args.command == "logs":
        for line in read_logs(args.run_id, log_dir=args.log_dir):
            print(line)
        return 0

    if args.command == "resume":
        asyncio.run(resume_run(args.run_id, runtime_dir=args.runtime_dir))
        print(f"Resume signal sent for {args.run_id}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def run() -> None:
    raise SystemExit(main())
```

Modify `inspectl/__init__.py` to:

```python
from inspectl.decorators import pipeline, step
from inspectl.logging import StepContext
from inspectl.models import PipelineState, RetryPolicy
from inspectl.polling import PollPolicy, async_poll_until, poll_until
from inspectl.runtime import run

__all__ = [
    "PipelineState",
    "PollPolicy",
    "RetryPolicy",
    "StepContext",
    "async_poll_until",
    "pipeline",
    "poll_until",
    "run",
    "step",
]
```

- [ ] **Step 5: Run the CLI tests**

Run:

```bash
pytest -q tests/inspectl/test_cli.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add inspectl/inspection.py inspectl/cli.py inspectl/__init__.py tests/inspectl/test_cli.py
git commit -m "feat: add inspectl inspection cli"
```

### Task 7: Write Docs, Wire The Quickstart, And Run Full Verification

**Files:**
- Modify: `README.md`
- Create: `docs/inspectl/README.md`
- Verify: `tests/inspectl/test_models.py`
- Verify: `tests/inspectl/test_decorators.py`
- Verify: `tests/inspectl/test_logging.py`
- Verify: `tests/inspectl/test_polling.py`
- Verify: `tests/inspectl/test_local_server.py`
- Verify: `tests/inspectl/test_cli.py`
- Verify: `tests/inspectl/integration/test_run_complete.py`
- Verify: `tests/inspectl/integration/test_run_pause_resume.py`

- [ ] **Step 1: Update the root README**

Modify `README.md` by appending:

```md
## Inspectl

`inspectl` is a local-first Temporal facade for state-threaded Python pipelines.

Public API:

- `@step`
- `@pipeline`
- `run(...)`
- `inspectl ...`

See `docs/inspectl/README.md` for the quickstart and debugging workflow.
```

- [ ] **Step 2: Add the inspectl quickstart**

Create `docs/inspectl/README.md` with:

```md
# Inspectl

`inspectl` keeps pipeline business logic prominent while using Temporal underneath for retries, durability, and pause/resume.

## Quickstart

```python
from dataclasses import dataclass

from inspectl import PipelineState, pipeline, run, step


@dataclass
class DemoState(PipelineState):
    value: int = 0


@step()
def increment(state: DemoState) -> DemoState:
    state.value += 1
    return state


@pipeline(name="demo")
async def demo_pipeline(state: DemoState) -> DemoState:
    state = await increment(state)
    return state


if __name__ == "__main__":
    result = run(demo_pipeline, DemoState(run_id="demo-run-001"))
    print(result.value)
```

## Operator Commands

- `inspectl inspect <run_id>`
- `inspectl logs <run_id>`

## Runtime Layout

- `.inspectl/runtime/temporal.sqlite` - local Temporal persistence
- `.inspectl/runtime/server.json` - local dev-server metadata
- `runs/<run_id>/session.jsonl` - append-only run log
- `runs/<run_id>/state_snapshots/*.json` - per-step snapshots
```

- [ ] **Step 3: Run the full inspectl test suite**

Run:

```bash
pytest -q \
  tests/inspectl/test_models.py \
  tests/inspectl/test_decorators.py \
  tests/inspectl/test_logging.py \
  tests/inspectl/test_polling.py \
  tests/inspectl/test_local_server.py \
  tests/inspectl/test_cli.py \
  tests/inspectl/integration/test_run_complete.py \
  tests/inspectl/integration/test_run_pause_resume.py
```

Expected: all tests pass.

- [ ] **Step 4: Smoke the CLI entrypoint**

Run:

```bash
python -m inspectl.cli logs demo-run-001 --log-dir runs
```

Expected: command exits 0. It may print nothing if no run exists yet, but it must not crash.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/inspectl/README.md
git commit -m "docs: add inspectl quickstart"
```

## Spec Coverage Check

- `@step`, `@pipeline`, `run(...)`, and `inspectl` surface: covered by Tasks 2, 5, and 6.
- Temporal-native implementation with one generic workflow and one dynamic activity: covered by Task 4.
- Local-first persistent Temporal server: covered by Task 5.
- Paused-workflow resume model: covered by Task 5 integration test.
- Local JSONL session logs and snapshots: covered by Task 3 and Task 4.
- Inspection CLI: covered by Task 6.
- Docs and onboarding path: covered by Task 7.

## Placeholder Scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task names exact files and commands.
- Every code-writing step includes concrete code to add.

## Type Consistency Check

- `PipelineState`, `RetryPolicy`, `StepContext`, `PollPolicy`, `InspectlPipelineWorkflow`, and `inspectl_step_activity` are defined once and reused consistently across tasks.
- Durable step routing uses the same `StepDefinition` type in decorators, workflow runtime, and activity runtime.
- The CLI surface stays `inspectl list`, `inspectl inspect`, `inspectl logs`, and `inspectl resume` throughout the plan.
