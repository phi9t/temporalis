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
    if existing is not None:
        raise DuplicateStepNameError(f"step name '{definition.name}' is already registered")
    _STEPS[definition.name] = definition
    return definition


def register_pipeline(definition: PipelineDefinition) -> PipelineDefinition:
    if definition.name in _PIPELINES:
        raise DuplicateStepNameError(
            f"pipeline name '{definition.name}' is already registered"
        )
    _PIPELINES[definition.name] = definition
    return definition


def get_step(name: str) -> StepDefinition:
    return _STEPS[name]


def get_pipeline(name: str) -> PipelineDefinition:
    return _PIPELINES[name]
