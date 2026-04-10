from __future__ import annotations

import inspect
from collections.abc import Awaitable
from contextvars import ContextVar, Token
from functools import wraps
from typing import Any, Protocol

from inspectl.errors import PipelineDefinitionError
from inspectl.models import RetryPolicy
from inspectl.registry import (
    PipelineDefinition,
    StepDefinition,
    register_pipeline,
    register_step,
)


class StepDispatcher(Protocol):
    def call_step(
        self, definition: StepDefinition, state: Any, *args: Any, **kwargs: Any
    ) -> Awaitable[Any]:
        ...


_DISPATCHER: ContextVar[StepDispatcher | None] = ContextVar(
    "inspectl_dispatcher", default=None
)


def current_dispatcher() -> StepDispatcher | None:
    return _DISPATCHER.get()


def set_dispatcher(dispatcher: StepDispatcher | None) -> Token[StepDispatcher | None]:
    return _DISPATCHER.set(dispatcher)


def reset_dispatcher(token: Token[StepDispatcher | None]) -> None:
    try:
        _DISPATCHER.reset(token)
    except ValueError:
        # Temporal workflow teardown can resume cleanup in a different Context
        # during GeneratorExit. In that case, restore the safe default instead
        # of surfacing an unraisable cross-context token reset error.
        _DISPATCHER.set(None)


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
        def wrapper(state, *args, **kwargs) -> Any | Awaitable[Any]:
            dispatcher = current_dispatcher()
            if dispatcher is None or definition.transient:
                return fn(state, *args, **kwargs)
            return dispatcher.call_step(definition, state, *args, **kwargs)

        wrapper._inspectl_step = definition  # type: ignore[attr-defined]
        return wrapper

    return decorate


def pipeline(*, name: str, owner: str | None = None, description: str | None = None):
    def decorate(fn):
        if not inspect.iscoroutinefunction(fn):
            raise PipelineDefinitionError(f"pipeline '{name}' must be async")

        register_pipeline(
            PipelineDefinition(name=name, fn=fn, owner=owner, description=description)
        )

        @wraps(fn)
        async def wrapper(state, *args, **kwargs):
            return await fn(state, *args, **kwargs)

        wrapper._inspectl_pipeline_name = name  # type: ignore[attr-defined]
        return wrapper

    return decorate
