from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import pytest
from temporalio import activity
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

ROOT = Path(__file__).resolve().parents[1]
KILVIN_PY = ROOT / "kilvin-py"
sys.path.insert(0, str(KILVIN_PY))

import start_workflow  # noqa: E402
from kilvin_py import activities, models  # noqa: E402
from kilvin_py.k8s_manifest import render_job_manifest  # noqa: E402
from kilvin_py.workflows import KilvinTrainingWorkflow  # noqa: E402


def test_sample_run_config_is_the_single_training_intent() -> None:
    config = start_workflow.sample_run_config()

    assert config.kilvin_run_name == "model-x-fineweb-64xa100"
    assert config.stage_sequence == ["pretrain"]
    assert len(config.stages) == 1
    assert config.stages[0].dataset_profile.uri == start_workflow.INTENT_DATASET_URI
    assert start_workflow.workflow_id_for_run("run-demo") == "kilvin-training-run-demo"
    assert start_workflow.TASK_QUEUE == "kilvin-training-task-queue"
    assert "laptop" in (start_workflow.sample_run_config.__doc__ or "").lower()


def test_interpret_intent_derives_the_laptop_scale_plan() -> None:
    config = start_workflow.sample_run_config()
    intent = asyncio.run(
        activities.interpret_training_intent(
            models.InterpretIntentInput(
                run_config=config,
                job_params_uri=f"hdfs://params/{config.run_id}/params.yaml",
            )
        )
    )

    assert intent.component_profile["model"] == "model-x"
    assert intent.image_ref == f"localhost:5001/kilvin-trainer:{config.run_id}"
    env = intent.trainer_env or {}
    assert env["MAX_STEPS"] == "200"
    assert env["TRAIN_STAGE"] == "pretrain"
    assert env["RUN_ID"] == config.run_id
    assert int(env["N_LAYER"]) >= 1
    assert intent.cpus == 2 and intent.memory_gb == 4


def test_interpret_intent_respects_laptop_max_steps_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KILVIN_LAPTOP_MAX_STEPS", "12")
    config = start_workflow.sample_run_config()

    intent = asyncio.run(
        activities.interpret_training_intent(
            models.InterpretIntentInput(
                run_config=config,
                job_params_uri=f"hdfs://params/{config.run_id}/params.yaml",
            )
        )
    )

    assert (intent.trainer_env or {})["MAX_STEPS"] == "12"


def test_materialize_renders_the_literal_job_manifest() -> None:
    allocation = models.ResourceAllocationOutput(
        allocation_id="alloc-1",
        cluster="local-k3s",
        cpus=2,
        memory_gb=4,
        dataset_mount="hdfs://d",
    )
    bundle = asyncio.run(
        activities.materialize_training_bundle(
            models.MaterializeTrainingBundleInput(
                ir_name="kilvin-ir-run-a-pretrain",
                checkpoint="s3://checkpoints/model-x/base",
                config_snapshot="file://./.kilvin-cache/run-a/workflow.yaml",
                allocation=allocation,
                stage_index=0,
                train_stage="pretrain",
                task_type="train",
                image_ref="localhost:5001/kilvin-trainer@sha256:abc",
                trainer_env={"MAX_STEPS": "200", "RUN_ID": "run-a"},
                model="model-x",
                run_id="run-a",
            )
        )
    )

    manifest = bundle.job_manifest
    assert manifest["spec"]["backoffLimit"] == 0
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "localhost:5001/kilvin-trainer@sha256:abc"
    assert {"name": "MAX_STEPS", "value": "200"} in container["env"]
    assert bundle.env_vars["CHECKPOINT_URI"] == "s3://checkpoints/model-x/base"


def test_workflow_persists_explorer_artifact_names() -> None:
    workflow_source = (KILVIN_PY / "kilvin_py" / "workflows.py").read_text(encoding="utf-8")
    readme = (KILVIN_PY / "README.md").read_text(encoding="utf-8")

    for artifact in ["quota_decision", "env_vars", "logs"]:
        assert f'artifact_label="{artifact}"' in workflow_source
        assert f"{artifact}.yaml" in readme

    assert "kilvin-training-run-<id>" in readme
    assert "CMD" not in readme
    assert "outer loop" not in readme.lower()


def _fake_activities() -> list:
    @activity.defn(name="interpret_training_intent")
    async def fake_interpret(input: models.InterpretIntentInput) -> models.TrainingIntent:
        return models.TrainingIntent(
            model_output_tos_key=input.job_params_uri,
            workflow_config_uri="file://./.kilvin-cache/test/workflow.yaml",
            checkpoint="s3://checkpoints/model-x/base",
            stage_index=0,
            component_profile={
                "model": "model-x",
                "run_name": "t",
                "dataset_root": "d",
                "spec_version": "v",
            },
            image_ref="localhost:5001/kilvin-trainer:test",
            trainer_env={"MAX_STEPS": "1"},
        )

    @activity.defn(name="concretize_dependencies")
    async def fake_concretize(
        input: models.ConcretizeDependenciesInput,
    ) -> models.ConcretizeDependenciesOutput:
        return models.ConcretizeDependenciesOutput(
            image_ref=input.image_ref,
            image_digest="sha256:fake",
            lockfile_sha256="fake",
        )

    @activity.defn(name="allocate_resources")
    async def fake_allocate(input: models.AllocateResourcesInput) -> models.ResourceAllocationOutput:
        return models.ResourceAllocationOutput(
            allocation_id="alloc-fake",
            cluster="local-k3s",
            cpus=input.cpus,
            memory_gb=input.memory_gb,
        )

    @activity.defn(name="materialize_training_bundle")
    async def fake_materialize(
        input: models.MaterializeTrainingBundleInput,
    ) -> models.MaterializedBundleOutput:
        manifest = render_job_manifest(
            job_name="kilvin-test",
            namespace=input.namespace,
            image=input.image_ref,
            env=input.trainer_env,
            cpus=input.allocation.cpus,
            memory_gb=input.allocation.memory_gb,
            run_id=input.run_id,
            stage_id=input.train_stage,
        )
        return models.MaterializedBundleOutput(
            bundle_id="bundle-fake",
            bundle_path="fake://bundle",
            job_manifest=manifest,
            env_vars=dict(input.trainer_env),
            launch_plan=[],
            health_checks=[],
        )

    @activity.defn(name="submit_k8s_job")
    async def fake_submit(input: models.SubmitK8sInput) -> models.SubmitK8sOutput:
        return models.SubmitK8sOutput(
            job_name="kilvin-test",
            job_uid="uid-1",
            k8s_namespace=input.namespace,
        )

    @activity.defn(name="monitor_training")
    async def fake_monitor(input: models.MonitorTrainingInput) -> models.MonitorOutput:
        return models.MonitorOutput(final_status="SUCCESS", log_tail=["step=1 loss=4.2"])

    return [
        fake_interpret,
        fake_concretize,
        fake_allocate,
        fake_materialize,
        fake_submit,
        fake_monitor,
        activities.persist_yaml_artifact,
    ]


@pytest.mark.asyncio
async def test_workflow_orchestrates_six_steps_and_pause_resume_with_fakes(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        client: Client = env.client
        task_queue = f"kilvin-test-{uuid.uuid4().hex[:6]}"
        config = start_workflow.sample_run_config()

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[KilvinTrainingWorkflow],
            activities=_fake_activities(),
        ):
            handle = await client.start_workflow(
                KilvinTrainingWorkflow.run,
                models.TrainingWorkflowInput(run_id=config.run_id, run_config=config),
                id=f"kilvin-test-{config.run_id}",
                task_queue=task_queue,
            )
            await handle.signal(KilvinTrainingWorkflow.pause)
            status = await handle.query(KilvinTrainingWorkflow.run_status)
            assert status.paused is True
            await handle.signal(KilvinTrainingWorkflow.resume)

            result = await handle.result()
            assert result == f"KILVIN_TRAINING_COMPLETED:{config.run_id}"

            trace = await handle.query(KilvinTrainingWorkflow.run_step_trace)
            succeeded = [t.step_name for t in trace if t.status == "SUCCEEDED"]
            assert succeeded == [
                "interpret_intent",
                "concretize_dependencies",
                "allocate_resources",
                "materialize_training_bundle",
                "submit_k8s_job",
                "monitor_training",
            ]
    finally:
        await env.shutdown()
