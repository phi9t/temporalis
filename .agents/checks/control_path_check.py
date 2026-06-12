from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import replace

from temporalio.client import Client

from kilvin_py.config import KilvinSettings
from kilvin_py.models import PauseSignal, ResumeSignal, TrainingWorkflowInput
from kilvin_py.workflows import KilvinTrainingWorkflow
from start_workflow import TASK_QUEUE, sample_run_config, workflow_id_for_run


def tiny_run_config(run_id: str):
    config = sample_run_config()
    stage = config.stages[0]
    tiny_stage = replace(
        stage,
        runtime_profile=replace(stage.runtime_profile, max_steps=1),
    )
    return replace(config, run_id=run_id, stages=[tiny_stage])


async def connect() -> Client:
    return await Client.connect(KilvinSettings.load().temporal_address)


async def start_paused() -> None:
    client = await connect()
    run_id = f"control-{uuid.uuid4().hex[:8]}"
    workflow_id = workflow_id_for_run(run_id)
    handle = await client.start_workflow(
        KilvinTrainingWorkflow.run,
        TrainingWorkflowInput(
            run_id=run_id,
            run_config=tiny_run_config(run_id),
            job_params_uri=f"hdfs://params/{run_id}/params.yaml",
        ),
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )
    await handle.signal(KilvinTrainingWorkflow.pause, PauseSignal(reason="control path proof"))
    print(f"{workflow_id} {run_id}")


async def start_tiny(prefix: str) -> None:
    client = await connect()
    run_id = f"{prefix}-{uuid.uuid4().hex[:8]}"
    workflow_id = workflow_id_for_run(run_id)
    await client.start_workflow(
        KilvinTrainingWorkflow.run,
        TrainingWorkflowInput(
            run_id=run_id,
            run_config=tiny_run_config(run_id),
            job_params_uri=f"hdfs://params/{run_id}/params.yaml",
        ),
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )
    print(f"{workflow_id} {run_id}")


async def query_status(workflow_id: str) -> None:
    client = await connect()
    status = await client.get_workflow_handle(workflow_id).query(KilvinTrainingWorkflow.run_status)
    print(
        f"workflow_id={workflow_id} status={status.overall_status} "
        f"paused={status.paused} current_step={status.current_step}"
    )


async def resume_wait(workflow_id: str) -> None:
    client = await connect()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(KilvinTrainingWorkflow.resume, ResumeSignal(reason="control path proof"))
    result = await handle.result()
    print(f"result={result}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["start", "start-tiny", "query", "resume"])
    parser.add_argument("--workflow-id")
    parser.add_argument("--prefix", default="tiny")
    args = parser.parse_args()

    if args.mode == "start":
        await start_paused()
    elif args.mode == "start-tiny":
        await start_tiny(args.prefix)
    elif args.mode == "query":
        if not args.workflow_id:
            raise SystemExit("--workflow-id is required")
        await query_status(args.workflow_id)
    elif args.mode == "resume":
        if not args.workflow_id:
            raise SystemExit("--workflow-id is required")
        await resume_wait(args.workflow_id)


if __name__ == "__main__":
    asyncio.run(main())
