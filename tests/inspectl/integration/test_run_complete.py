from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from inspectl import PipelineState, pipeline, step
from inspectl.activity_runtime import inspectl_step_activity
from inspectl.registry import clear_registry
from inspectl.workflow_runtime import InspectlPipelineWorkflow


@dataclass
class ExampleState(PipelineState):
    build_id: str | None = None


@pytest.fixture(autouse=True)
def isolated_registry() -> None:
    clear_registry()
    yield
    clear_registry()


def register_demo_pipeline() -> None:
    @step(produces=["build_id"])
    def submit_compilation(state: ExampleState) -> ExampleState:
        state.build_id = "build-123"
        return state

    @step(produces=["build_id"])
    def finalize_build(
        state: ExampleState, suffix: str = "done", *, version: str = "v1"
    ) -> ExampleState:
        assert suffix == "release"
        assert version == "v2"
        state.build_id = f"{state.build_id}-{suffix}-{version}"
        return state

    @pipeline(name="demo-pipeline")
    async def demo_pipeline(state: ExampleState) -> ExampleState:
        state = await submit_compilation(state)
        state = await finalize_build(state, "release", version="v2")
        return state


def register_precondition_pipeline() -> None:
    @step(requires=["build_id"])
    def publish_build(state: ExampleState) -> ExampleState:
        state.build_id = f"{state.build_id}-published"
        return state

    @pipeline(name="precondition-pipeline")
    async def precondition_pipeline(state: ExampleState) -> ExampleState:
        state = await publish_build(state)
        return state


async def _execute_pipeline(
    env: WorkflowEnvironment, *, pipeline_name: str, run_id: str, log_dir: Path
) -> dict:
    return await asyncio.wait_for(
        env.client.execute_workflow(
            InspectlPipelineWorkflow.run,
            {
                "pipeline_name": pipeline_name,
                "state": ExampleState(run_id=run_id).to_dict(),
                "log_dir": str(log_dir),
            },
            id=run_id,
            task_queue="inspectl-demo",
        ),
        timeout=10,
    )


def _exception_chain_text(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        parts.append(str(current))
        current = getattr(current, "cause", None)
    return " | ".join(parts)


@pytest.mark.asyncio
async def test_generic_workflow_executes_step_activity(tmp_path: Path) -> None:
    register_demo_pipeline()

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
            result = await _execute_pipeline(
                env,
                pipeline_name="demo-pipeline",
                run_id="run-001",
                log_dir=tmp_path / "runs",
            )

    restored = ExampleState.from_dict(result)
    assert restored.build_id == "build-123-release-v2"
    assert (
        tmp_path / "runs" / "run-001" / "state_snapshots" / "002_finalize_build.json"
    ).exists()


@pytest.mark.asyncio
async def test_generic_workflow_fails_visible_on_precondition_error(tmp_path: Path) -> None:
    register_precondition_pipeline()

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
            with pytest.raises(WorkflowFailureError) as exc_info:
                await _execute_pipeline(
                    env,
                    pipeline_name="precondition-pipeline",
                    run_id="run-002",
                    log_dir=tmp_path / "runs",
                )

    assert "requires 'build_id'" in _exception_chain_text(exc_info.value)
