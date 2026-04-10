from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass

import pytest

from inspectl.decorators import pipeline, reset_dispatcher, set_dispatcher, step
from inspectl.errors import DuplicateStepNameError, PipelineDefinitionError
from inspectl.models import PipelineState
from inspectl.registry import clear_registry


@dataclass
class ExampleState(PipelineState):
    value: int = 0


@pytest.fixture(autouse=True)
def isolated_registry() -> None:
    clear_registry()
    yield
    clear_registry()


def test_step_runs_directly_outside_dispatch_context() -> None:
    @step()
    def increment(state: ExampleState) -> ExampleState:
        state.value += 1
        return state

    result = increment(ExampleState(run_id="run-001"))

    assert result.value == 1


def test_durable_step_routes_through_dispatcher_and_is_awaitable() -> None:
    calls: list[str] = []

    @step(name="durable")
    def increment(state: ExampleState) -> ExampleState:
        raise AssertionError("durable step should not execute directly")

    class FakeDispatcher:
        def call_step(self, definition, state):
            calls.append(definition.name)

            async def invoke() -> ExampleState:
                state.value += 1
                return state

            return invoke()

    token = set_dispatcher(FakeDispatcher())
    try:
        result = increment(ExampleState(run_id="run-002"))
        assert inspect.isawaitable(result)
        restored = asyncio.run(result)
    finally:
        reset_dispatcher(token)

    assert calls == ["durable"]
    assert restored.value == 1


def test_duplicate_step_names_raise() -> None:
    @step(name="shared")
    def first(state: ExampleState) -> ExampleState:
        return state

    with pytest.raises(DuplicateStepNameError):
        @step(name="shared")
        def second(state: ExampleState) -> ExampleState:
            return state


def test_duplicate_pipeline_names_raise() -> None:
    @pipeline(name="shared-pipeline")
    async def first(state: ExampleState) -> ExampleState:
        return state

    with pytest.raises(DuplicateStepNameError):
        @pipeline(name="shared-pipeline")
        async def second(state: ExampleState) -> ExampleState:
            return state


def test_pipeline_must_be_async() -> None:
    with pytest.raises(PipelineDefinitionError):
        @pipeline(name="bad-pipeline")
        def not_async(state: ExampleState) -> ExampleState:
            return state
