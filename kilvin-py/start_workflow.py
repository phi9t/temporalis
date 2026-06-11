import asyncio
import uuid

from temporalio.client import Client

from kilvin_py import models
from kilvin_py.workflows import ParentKilvinCmdWorkflow


def sample_run_config() -> models.RunConfig:
    return models.RunConfig(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        kilvin_run_name="k2-2x-foundation-baseline",
        workflow_spec="kilvin-foundation-v1",
        policy=models.RunPolicy(
            max_stage_retries=2,
            stage_timeout_minutes=1440,
            purge_on_success=True,
            preserve_artifacts_on_failure=True,
            pause_on_step_failure=True,
            max_step_replay_attempts=3,
            artifact_store_uri="file://./.kilvin-artifacts",
        ),
        stage_sequence=[
            "vit_pretrain",
            "joint_pretrain",
            "continue_pretrain",
            "long_context_midtrain",
            "parl_rl",
            "agentic_synthesis",
            "qat",
        ],
        stages=[
            models.StageConfig(
                stage_id="vit_pretrain",
                stage_type="pretrain",
                phase="foundation",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/vit_pretrain",
                    min_examples=50_000_000,
                    token_budget=1_000_000_000_000,
                    token_budget_tolerance_ratio=0.05,
                    mix_requirements={"visual": 1.0},
                    quality_thresholds={"recall": 0.97},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=1_000_000_000_000,
                    max_steps=80_000,
                    global_batch_tokens=262_144,
                    learning_rate=0.0002,
                    optimizer="adamw",
                    precision="bf16",
                ),
            ),
            models.StageConfig(
                stage_id="joint_pretrain",
                stage_type="continued_pretrain",
                phase="foundation",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/joint_pretrain",
                    min_examples=600_000_000,
                    token_budget=15_000_000_000_000,
                    token_budget_tolerance_ratio=0.08,
                    mix_requirements={"text": 0.55, "code": 0.2, "science": 0.15, "visual": 0.1},
                    quality_thresholds={"quality": 0.98},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=15_000_000_000_000,
                    max_steps=1_200_000,
                    global_batch_tokens=524_288,
                    learning_rate=0.0001,
                ),
            ),
            models.StageConfig(
                stage_id="continue_pretrain",
                stage_type="continued_pretrain",
                phase="foundation",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/continue_pretrain",
                    min_examples=300_000_000,
                    token_budget=15_000_000_000_000,
                    token_budget_tolerance_ratio=0.1,
                    mix_requirements={"text": 0.5, "code": 0.35, "science": 0.15},
                    quality_thresholds={"quality": 0.97},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=15_000_000_000_000,
                    max_steps=900_000,
                    global_batch_tokens=524_288,
                    learning_rate=8e-05,
                ),
            ),
            models.StageConfig(
                stage_id="long_context_midtrain",
                stage_type="context_extension",
                phase="foundation",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/long_context_midtrain",
                    min_examples=25_000_000,
                    token_budget=700_000_000_000,
                    token_budget_tolerance_ratio=0.05,
                    mix_requirements={"text": 0.75, "code": 0.2, "math": 0.05},
                    quality_thresholds={"quality": 0.97},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=700_000_000_000,
                    max_steps=500_000,
                    global_batch_tokens=1_048_576,
                    learning_rate=7e-05,
                    precision="bf16",
                ),
            ),
            models.StageConfig(
                stage_id="parl_rl",
                stage_type="rl",
                phase="post_foundation",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/parl_rl",
                    min_examples=2_000_000,
                    token_budget=120_000_000_000,
                    token_budget_tolerance_ratio=0.1,
                    mix_requirements={"tooling": 0.6, "dialogue": 0.4},
                    quality_thresholds={"reward_fidelity": 0.95},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=120_000_000_000,
                    max_steps=240_000,
                    global_batch_tokens=262_144,
                    learning_rate=3e-05,
                ),
            ),
            models.StageConfig(
                stage_id="agentic_synthesis",
                stage_type="agentic_data_synthesis",
                phase="post_foundation",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/agentic_data_synthesis",
                    min_examples=5_000_000,
                    token_budget=60_000_000_000,
                    token_budget_tolerance_ratio=0.15,
                    mix_requirements={"tool_call": 0.5, "reasoning": 0.5},
                    quality_thresholds={"trajectory_validity": 0.96},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=60_000_000_000,
                    max_steps=120_000,
                    global_batch_tokens=131_072,
                    learning_rate=2.5e-05,
                ),
            ),
            models.StageConfig(
                stage_id="qat",
                stage_type="quantization_fine_tune",
                phase="post_foundation",
                enabled=True,
                dataset_profile=models.StageDatasetProfile(
                    uri="hdfs://datasets/qat",
                    min_examples=5_000_000,
                    token_budget=20_000_000_000,
                    token_budget_tolerance_ratio=0.1,
                    mix_requirements={"math": 0.3, "code": 0.5, "science": 0.2},
                    quality_thresholds={"distillation_fidelity": 0.97},
                ),
                runtime_profile=models.StageRuntimeProfile(
                    total_tokens_target=20_000_000_000,
                    max_steps=80_000,
                    global_batch_tokens=65_536,
                    learning_rate=1e-05,
                    precision="int4",
                ),
            ),
        ],
    )


async def main() -> None:
    client = await Client.connect("localhost:7233")
    run_config = sample_run_config()
    run_id = run_config.run_id
    result = await client.execute_workflow(
        ParentKilvinCmdWorkflow.run,
        models.StartKilvinCommandInput(
            run_config=run_config,
            cmd_name="k2.5-continuation",
            job_params_uri=f"hdfs://params/{run_id}/params.yaml",
        ),
        id=f"kilvin-parent-{run_id}",
        task_queue="kilvin-training-task-queue",
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
