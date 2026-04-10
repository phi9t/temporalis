from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from temporalio.client import Client, WorkflowHandle
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker

from inspectl.activity_runtime import inspectl_step_activity
from inspectl.errors import PipelinePaused
from inspectl.local_server import LocalServerManager
from inspectl.logging import RunSession
from inspectl.models import PipelineState, RuntimeConfig
from inspectl.workflow_runtime import InspectlPipelineWorkflow


async def _connect_with_retries(
    *,
    target: str,
    namespace: str,
    ownership_check,
) -> Client:
    last_error: Exception | None = None
    for _ in range(25):
        if not ownership_check():
            raise RuntimeError(
                "inspectl local Temporal server is not owned by this workspace or is no longer running"
            )
        try:
            return await Client.connect(target, namespace=namespace)
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(0.2)

    assert last_error is not None
    raise last_error


async def _query_until_paused(handle: WorkflowHandle[Any, Any]) -> dict[str, Any]:
    while True:
        try:
            description = await asyncio.wait_for(
                handle.query(InspectlPipelineWorkflow.describe),
                timeout=1.0,
            )
        except asyncio.TimeoutError:
            await asyncio.sleep(0.2)
            continue
        if description["status"] == "paused":
            return description
        await asyncio.sleep(0.2)


async def _connect_local_server(config: RuntimeConfig) -> Client:
    manager = LocalServerManager(config)
    details = manager.read_state()

    if manager.is_runtime_state_valid(details):
        assert details is not None
        return await _connect_with_retries(
            target=details["target"],
            namespace=config.namespace,
            ownership_check=lambda: manager.is_runtime_state_valid(details),
        )

    details = manager.start()
    return await _connect_with_retries(
        target=details["target"],
        namespace=config.namespace,
        ownership_check=lambda: manager.is_runtime_state_valid(details),
    )


def _pipeline_name(pipeline_fn: Any) -> str:
    pipeline_name = getattr(pipeline_fn, "_inspectl_pipeline_name", None)
    if not isinstance(pipeline_name, str) or not pipeline_name:
        raise TypeError("run_async() requires a function decorated with @pipeline")
    return pipeline_name


def _task_queue(config: RuntimeConfig, pipeline_name: str) -> str:
    return f"{config.task_queue_prefix}-{pipeline_name}"


def _workflow_payload(
    *, pipeline_name: str, state: PipelineState, log_dir: Path | str
) -> dict[str, Any]:
    return {
        "pipeline_name": pipeline_name,
        "state": state.to_dict(),
        "log_dir": str(log_dir),
    }


async def _start_or_resume(
    *,
    client: Client,
    pipeline_name: str,
    state: PipelineState,
    task_queue: str,
    log_dir: Path | str,
    resume: bool,
) -> WorkflowHandle[Any, Any]:
    handle = client.get_workflow_handle(state.run_id)
    if resume:
        description = await handle.describe()
        if description.task_queue != task_queue:
            raise RuntimeError(
                f"run_id '{state.run_id}' belongs to a different pipeline "
                f"(expected task queue '{task_queue}', found '{description.task_queue}')"
            )
        await handle.signal(InspectlPipelineWorkflow.resume)
        return handle

    try:
        return await client.start_workflow(
            InspectlPipelineWorkflow.run,
            _workflow_payload(pipeline_name=pipeline_name, state=state, log_dir=log_dir),
            id=state.run_id,
            task_queue=task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        description = await handle.describe()
        if description.task_queue != task_queue:
            raise RuntimeError(
                f"run_id '{state.run_id}' already exists for a different pipeline "
                f"(expected task queue '{task_queue}', found '{description.task_queue}')"
            )
        raise RuntimeError(
            f"run_id '{state.run_id}' already exists; use resume=True to continue it"
        )


async def run_async(
    pipeline_fn: Any,
    state: PipelineState,
    *,
    client: Client | None = None,
    resume: bool = False,
    log_dir: Path | str = Path("runs"),
    config: RuntimeConfig | None = None,
) -> PipelineState:
    config = config or RuntimeConfig()
    pipeline_name = _pipeline_name(pipeline_fn)
    session = RunSession(run_id=state.run_id, root_dir=Path(log_dir))
    if client is None:
        client = await _connect_local_server(config)

    worker = Worker(
        client,
        task_queue=_task_queue(config, pipeline_name),
        workflows=[InspectlPipelineWorkflow],
        activities=[inspectl_step_activity],
    )

    session.record(
        level="INFO",
        event="run.start",
        message="starting inspectl pipeline runtime",
        data={"pipeline": pipeline_name, "resume": resume},
    )

    try:
        async with worker:
            handle = await _start_or_resume(
                client=client,
                pipeline_name=pipeline_name,
                state=state,
                task_queue=_task_queue(config, pipeline_name),
                log_dir=log_dir,
                resume=resume,
            )
            result_task = asyncio.create_task(handle.result())
            paused_task = asyncio.create_task(_query_until_paused(handle))
            done, pending = await asyncio.wait(
                {result_task, paused_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            if paused_task in done:
                description = paused_task.result()
                session.record(
                    level="ERROR",
                    event="run.paused",
                    message="workflow paused awaiting resume",
                    data=description,
                )
                raise PipelinePaused(description.get("failure_reason") or "workflow paused")

            result = result_task.result()
            session.record(
                level="INFO",
                event="run.complete",
                message="workflow completed",
            )
            return type(state).from_dict(result)
    finally:
        session.close()


def run(pipeline_fn: Any, state: PipelineState, **kwargs: Any) -> PipelineState:
    return asyncio.run(run_async(pipeline_fn, state, **kwargs))
