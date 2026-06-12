import asyncio
import uuid

from temporalio.client import Client

from kilvin_py import models
from kilvin_py.workflows import KilvinTrainingWorkflow


def sample_run_config() -> models.RunConfig:
    """One clean request: train model X on FineWeb with 64 A100 GPUs.

    The single pretrain stage keeps the whole walkthrough inspectable: one
    allocation (8 nodes x 8 A100s), one materialized bundle, one Kubernetes
    job, and the hood-open artifacts the explorer points at (quota decision,
    env vars, dataset path, job id, logs).
    """

    return models.RunConfig(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        kilvin_run_name="model-x-fineweb-64xa100",
        workflow_spec="kilvin-training-v1",
        policy=models.RunPolicy(
            max_stage_retries=2,
            stage_timeout_minutes=1440,
            purge_on_success=True,
            preserve_artifacts_on_failure=True,
            pause_on_step_failure=True,
            max_step_replay_attempts=3,
            artifact_store_uri="file://./.kilvin-artifacts",
        ),
        stage_sequence=["pretrain"],
        stages=[
            models.StageConfig(
                stage_id="pretrain",
                stage_type="pretrain",
                phase="train",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/fineweb",
                    min_examples=1_000_000_000,
                    token_budget=15_000_000_000_000,
                    token_budget_tolerance_ratio=0.05,
                    mix_requirements={"web_text": 1.0},
                    quality_thresholds={"quality": 0.97},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=15_000_000_000_000,
                    max_steps=1_200_000,
                    global_batch_tokens=524_288,
                    learning_rate=0.0001,
                    optimizer="adamw",
                    precision="bf16",
                ),
            ),
        ],
    )


async def main() -> None:
    client = await Client.connect("localhost:7233")
    run_config = sample_run_config()
    run_id = run_config.run_id
    result = await client.execute_workflow(
        KilvinTrainingWorkflow.run,
        models.TrainingWorkflowInput(
            run_id=run_id,
            run_config=run_config,
            job_params_uri=f"hdfs://params/{run_id}/params.yaml",
        ),
        id=f"kilvin-training-{run_id}",
        task_queue="kilvin-training-task-queue",
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
