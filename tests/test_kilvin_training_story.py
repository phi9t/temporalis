from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KILVIN_PY = ROOT / "kilvin-py"
sys.path.insert(0, str(KILVIN_PY))

import start_workflow  # noqa: E402
from kilvin_py import activities, models  # noqa: E402


def test_sample_run_config_is_the_single_training_intent() -> None:
    config = start_workflow.sample_run_config()

    assert config.kilvin_run_name == "model-x-fineweb-64xa100"
    assert config.stage_sequence == ["pretrain"]
    assert len(config.stages) == 1
    assert config.stages[0].dataset_profile.uri == start_workflow.INTENT_DATASET_URI
    assert start_workflow.INTENT_GPU_COUNT == start_workflow.INTENT_NODE_COUNT * start_workflow.INTENT_GPUS_PER_NODE
    assert start_workflow.workflow_id_for_run("run-demo") == "kilvin-training-run-demo"
    assert start_workflow.TASK_QUEUE == "kilvin-training-task-queue"


def test_activities_materialize_the_same_hood_open_story() -> None:
    config = start_workflow.sample_run_config()
    stage = config.stages[0]

    intent = asyncio.run(
        activities.interpret_training_intent(
            models.InterpretIntentInput(
                run_config=config,
                job_params_uri=f"hdfs://params/{config.run_id}/params.yaml",
            )
        )
    )
    assert intent.checkpoint == "s3://checkpoints/model-x/base"
    assert intent.component_profile["model"] == start_workflow.INTENT_MODEL
    assert intent.component_profile["dataset_root"] == start_workflow.INTENT_DATASET_URI

    allocation = asyncio.run(
        activities.allocate_resources(
            models.AllocateResourcesInput(
                run_id=config.run_id,
                stage_id=stage.stage_id,
                stage_index=0,
                dataset_uri=stage.dataset_profile.uri,
                node_count=start_workflow.INTENT_NODE_COUNT,
                gpus_per_node=start_workflow.INTENT_GPUS_PER_NODE,
            )
        )
    )
    assert allocation.rank_size == 64
    assert allocation.dataset_mount == "fsx://us-east-train-7/fineweb/pretrain"
    assert allocation.quota_decision is not None
    assert allocation.quota_decision.cluster == "us-east-train-7"
    assert allocation.quota_decision.gpus_requested == 64
    assert "s3://fineweb-us-east" in allocation.quota_decision.data_locality
    assert "InfiniBand" in allocation.quota_decision.reason

    bundle = asyncio.run(
        activities.materialize_training_bundle(
            models.MaterializeTrainingBundleInput(
                ir_name=f"kilvin-ir-{config.run_id}-pretrain",
                checkpoint=intent.checkpoint or "s3://checkpoints/model-x/base",
                config_snapshot=intent.workflow_config_uri,
                allocation=allocation,
                stage_index=0,
                train_stage=stage.stage_id,
                task_type="train",
                total_tokens_target=stage.runtime_profile.total_tokens_target,
                global_batch_tokens=stage.runtime_profile.global_batch_tokens,
                max_steps=stage.runtime_profile.max_steps,
                learning_rate=stage.runtime_profile.learning_rate,
                model=intent.component_profile["model"],
            )
        )
    )
    assert bundle.env_vars["MODEL_NAME"] == "model-x"
    assert bundle.env_vars["DATASET_MOUNT"] == "fsx://us-east-train-7/fineweb/pretrain"
    assert bundle.env_vars["WORLD_SIZE"] == "64"
    assert bundle.launch_plan[0]["entrypoint"] == "kilvin-train"
    assert "--stage" in bundle.launch_plan[0]["args"]
    assert "rdma-topology" in bundle.health_checks


def test_workflow_persists_explorer_artifact_names() -> None:
    workflow_source = (KILVIN_PY / "kilvin_py" / "workflows.py").read_text(encoding="utf-8")
    readme = (KILVIN_PY / "README.md").read_text(encoding="utf-8")

    for artifact in ["quota_decision", "env_vars", "logs"]:
        assert f'artifact_label="{artifact}"' in workflow_source
        assert f"{artifact}.yaml" in readme

    assert "kilvin-training-run-<id>" in readme
    assert "CMD" not in readme
    assert "outer loop" not in readme.lower()


def test_workflow_skip_paths_preserve_the_same_training_intent() -> None:
    workflow_source = (KILVIN_PY / "kilvin_py" / "workflows.py").read_text(encoding="utf-8")

    assert 'checkpoint="s3://checkpoints/model-x/base"' in workflow_source
    assert '"model": "model-x"' in workflow_source
    assert '"dataset_root": stages[0].dataset_profile.uri' in workflow_source
    assert 'code_tos_key=intent.checkpoint or "s3://checkpoints/model-x/base"' in workflow_source
