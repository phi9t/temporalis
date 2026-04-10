from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from temporalio.client import WorkflowExecutionStatus
from temporalio.testing import WorkflowEnvironment

from inspectl import PipelineState, pipeline, step
from inspectl.errors import PipelinePaused
from inspectl.registry import clear_registry
from inspectl.runtime import run_async


@dataclass
class ExampleState(PipelineState):
    attempts: int = 0
    done: bool = False


GATE = {"open": False}


@pytest.fixture(autouse=True)
def isolated_registry() -> None:
    clear_registry()
    GATE["open"] = False
    yield
    clear_registry()
    GATE["open"] = False


def register_pause_pipeline():
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

    return pause_pipeline


def register_other_pipeline():
    @step(max_attempts=1)
    def other_step(state: ExampleState) -> ExampleState:
        state.done = True
        return state

    @pipeline(name="other-pipeline")
    async def other_pipeline(state: ExampleState) -> ExampleState:
        state = await other_step(state)
        return state

    return other_pipeline


@pytest.mark.asyncio
async def test_run_async_pauses_and_resumes_same_workflow(tmp_path: Path) -> None:
    pause_pipeline = register_pause_pipeline()

    async with await WorkflowEnvironment.start_local(
        dev_server_database_filename=str(tmp_path / "temporal.sqlite"),
    ) as env:
        with pytest.raises(PipelinePaused):
            await run_async(
                pause_pipeline,
                ExampleState(run_id="run-001"),
                client=env.client,
                resume=False,
                log_dir=tmp_path / "runs",
            )

        handle = env.client.get_workflow_handle("run-001")
        paused_execution = await handle.describe()

        GATE["open"] = True
        result = await run_async(
            pause_pipeline,
            ExampleState(run_id="run-001"),
            client=env.client,
            resume=True,
            log_dir=tmp_path / "runs",
        )

        completed_execution = await handle.describe()

    assert result.done is True
    assert result.attempts == 1
    assert paused_execution.status is WorkflowExecutionStatus.RUNNING
    assert completed_execution.status is WorkflowExecutionStatus.COMPLETED
    assert paused_execution.run_id == completed_execution.run_id


@pytest.mark.asyncio
async def test_run_async_resume_false_rejects_existing_run_id(tmp_path: Path) -> None:
    pause_pipeline = register_pause_pipeline()

    async with await WorkflowEnvironment.start_local(
        dev_server_database_filename=str(tmp_path / "temporal.sqlite"),
    ) as env:
        with pytest.raises(PipelinePaused):
            await run_async(
                pause_pipeline,
                ExampleState(run_id="run-duplicate"),
                client=env.client,
                resume=False,
                log_dir=tmp_path / "runs",
            )

        with pytest.raises(RuntimeError, match="resume=True"):
            await run_async(
                pause_pipeline,
                ExampleState(run_id="run-duplicate"),
                client=env.client,
                resume=False,
                log_dir=tmp_path / "runs",
            )


@pytest.mark.asyncio
async def test_run_async_resume_true_rejects_wrong_pipeline(tmp_path: Path) -> None:
    pause_pipeline = register_pause_pipeline()
    other_pipeline = register_other_pipeline()

    async with await WorkflowEnvironment.start_local(
        dev_server_database_filename=str(tmp_path / "temporal.sqlite"),
    ) as env:
        with pytest.raises(PipelinePaused):
            await run_async(
                pause_pipeline,
                ExampleState(run_id="run-mismatch"),
                client=env.client,
                resume=False,
                log_dir=tmp_path / "runs",
            )

        with pytest.raises(RuntimeError, match="different pipeline"):
            await run_async(
                other_pipeline,
                ExampleState(run_id="run-mismatch"),
                client=env.client,
                resume=True,
                log_dir=tmp_path / "runs",
            )
