from __future__ import annotations

import uuid

from temporalio import activity

from .artifacts import ArtifactStore
from .models import (
    AllocateResourcesInput,
    ArtifactWriteInput,
    CheckpointOutput,
    ConfigureTrainingDataInput,
    DataConfigureOutput,
    DevPrepareInput,
    DevPrepareOutput,
    ExtractStageConfigInput,
    ExtractStageConfigOutput,
    ExtractWorkflowConfigInput,
    ExtractWorkflowConfigOutput,
    MaterializedBundleOutput,
    MaterializeWorkloadBundleInput,
    MonitorOutput,
    MonitorTrainingInput,
    PipelineAllocation,
    PipelineBundleOutput,
    PurgeInput,
    ReamAllocationOutput,
    SubmitK8sInput,
    SubmitK8sOutput,
    StepIOArtifact,
)


@activity.defn
async def extract_workflow_config(
    input: ExtractWorkflowConfigInput,
) -> ExtractWorkflowConfigOutput:
    """Load workflow-level config and return the canonical typed extract output."""

    run_stages = input.run_config.stages
    stage_zero_dataset = run_stages[0].dataset_profile.uri if run_stages else "hdfs://datasets/k2/"
    stage_zero_checkpoint = run_stages[0].dataset_profile.uri if run_stages else "s3://models/k2/checkpoint"

    return ExtractWorkflowConfigOutput(
        model_output_tos_key=input.job_params_uri,
        workflow_config_uri=f"file://./.kilvin-cache/{input.run_config.run_id}/workflow.yaml",
        checkpoint=stage_zero_checkpoint,
        stage_index=0,
        component_profile={
            "command": input.cmd_name,
            "dataset_root": stage_zero_dataset,
            "spec_version": input.run_config.workflow_spec,
        },
    )


@activity.defn
async def extract_stage_config(input: ExtractStageConfigInput) -> ExtractStageConfigOutput:
    """Resolve the stage-local execution slice from the workflow snapshot."""

    pipelines = input.stage.pipelines or []
    total_nodes = sum(max(profile.node_count, 0) for profile in pipelines) or 1
    total_ranks = sum(max(profile.rank_size, 0) for profile in pipelines) or 1
    strategy = input.stage.pipeline_strategy
    return ExtractStageConfigOutput(
        stage_id=input.stage.stage_id,
        stage_index=input.stage_index,
        workflow_config_uri=input.workflow_config_uri,
        task_type=input.stage.stage_type,
        pipeline_count=max(len(pipelines), 1),
        pipeline_strategy_mode=strategy.mode if strategy else "serial",
        component_profile={
            "phase": input.stage.phase,
            "optimizer": input.stage.runtime_profile.optimizer,
            "precision": input.stage.runtime_profile.precision,
        },
        resource_shape_hint={
            "total_nodes": total_nodes,
            "total_ranks": total_ranks,
        },
    )


extract_cmd_config = extract_workflow_config


@activity.defn
async def dev_prepare(input: DevPrepareInput) -> DevPrepareOutput:
    return DevPrepareOutput(
        auto_job_id=f"kilvin-job-{uuid.uuid4().hex[:10]}",
        code_tos_key=f"{input.checkpoint or 'scratch'}/artifacts/code.tar.gz",
    )


@activity.defn
async def update_cmd_state(input: dict | object) -> None:
    """Persist command-level status for control-plane observability."""

    # Intentionally explicit placeholder. In production this writes to the state catalog.
    return None


@activity.defn
async def update_cmd_state_from_child(input: object) -> None:
    """Compatibility alias for alternate workflow call style."""

    return None


@activity.defn
async def validate_checkpoint(checkpoint_path: str) -> CheckpointOutput:
    path = checkpoint_path or "s3://models/k2/checkpoint"
    return CheckpointOutput(
        checkpoint_path=path,
        manifest_uri=f"{path}/manifest.yaml",
        model_size_estimate=700_000_000_000,
    )


@activity.defn
async def configure_training_data(input: ConfigureTrainingDataInput) -> DataConfigureOutput:
    mix = input.data_mix_requirements or {"text": 1.0}
    quality = input.quality_thresholds or {"overall": 0.99}
    return DataConfigureOutput(
        dataset_id=f"ds-{input.dataset_uri.replace('/', '_')[-12:]}",
        schema_version="v1",
        shard_count=max(1, (input.min_examples or 10_000) // 10000),
        estimated_tokens=max(input.required_token_budget, 0),
        stage_token_mix={k: int(v * 1000) for k, v in mix.items() if v >= 0},
        composition_breakdown=mix,
        quality_scores=quality,
        total_examples=max(input.min_examples or 0, 1_000),
        validation_report_path=f"{input.dataset_uri}/validation-report.yaml",
    )


@activity.defn
async def allocate_resources(input: AllocateResourcesInput) -> ReamAllocationOutput:
    allocations: list[PipelineAllocation] = []
    for profile in input.pipeline_profiles:
        allocations.append(
            PipelineAllocation(
                pipeline_id=profile.pipeline_id,
                component_name=profile.component_name,
                node_count=profile.node_count,
                gpus_per_node=profile.gpus_per_node,
                rank_size=profile.rank_size,
                machine_type=profile.machine_type or "h100-sxm",
                pool_name=profile.resource_pool or "foundation",
                rdma_enabled=bool(profile.rdma_profile),
                nccl_profile=profile.nccl_profile or "nccl",
                rendezvous={"control": "grpc://kilvin-controller:9001"},
            )
        )

    if not allocations:
        allocations.append(
            PipelineAllocation(
                pipeline_id="default-pipeline",
                component_name="foundation_model",
                node_count=64,
                gpus_per_node=8,
                rank_size=512,
                machine_type="h100-sxm",
                pool_name="foundation",
                rdma_enabled=True,
                nccl_profile="nccl",
                rendezvous={"control": "grpc://kilvin-controller:9001"},
            )
        )

    return ReamAllocationOutput(
        allocation_id=f"alloc-{uuid.uuid4().hex[:10]}",
        resource_epoch=1,
        pools_reservation_id=f"pool-{uuid.uuid4().hex[:8]}",
        pipeline_allocations=allocations,
    )


@activity.defn
async def materialize_workload_bundle(input: MaterializeWorkloadBundleInput) -> PipelineBundleOutput:
    launch_budget = {
        "total_tokens_target": input.total_tokens_target,
        "global_batch_tokens": input.global_batch_tokens,
        "max_steps": input.max_steps,
        "token_margin": int(input.total_tokens_target * 0.05),
        "learning_rate": int(input.learning_rate * 1e9),
    }

    runtime_setup = {
        "checkpoint": input.checkpoint,
        "task_type": input.task_type,
        "train_stage": input.train_stage,
        "model": input.model,
        "rdma_profile": input.allocation.pipeline_id,
        "nccl_profile": input.pipeline_profile.nccl_profile,
        "rdma_enabled": True,
        "max_seq_len": input.pipeline_profile.max_seq_len,
    }

    bound_components = [
        {
            "component": input.allocation.component_name,
            "machine_type": input.allocation.machine_type,
            "node_count": input.allocation.node_count,
            "gpus_per_node": input.allocation.gpus_per_node,
            "modality_mix": input.pipeline_profile.modality_mix,
        }
    ]

    return PipelineBundleOutput(
        pipeline_id=input.pipeline_id,
        bundle=MaterializedBundleOutput(
            bundle_id=f"bundle-{uuid.uuid4().hex[:10]}",
            bundle_path=f"{input.config_snapshot}/bundle/{input.pipeline_id}.yaml",
            bound_components=bound_components,
            runtime_setup=runtime_setup,
            rendezvous=dict(input.allocation.rendezvous or {}),
            launch_plan=[
                {
                    "entrypoint": "kilvin-train",
                    "args": ["--config", input.config_snapshot, "--stage", input.train_stage],
                }
            ],
            token_plan=launch_budget,
            health_checks=["nccl-rings", "kv-router", "data-loader", "rdma-topology"],
        ),
    )


materialize_training_bundle = materialize_workload_bundle


@activity.defn
async def submit_k8s_job(input: SubmitK8sInput) -> SubmitK8sOutput:
    namespace = input.namespace or "kilvin-training"
    return SubmitK8sOutput(
        auto_job_name=f"kilvin-{input.pipeline_id}-{uuid.uuid4().hex[:6]}",
        primus_job_id=f"p-{uuid.uuid4().hex[:12]}",
        primus_ui_url=f"https://primus.local/kilvin/{uuid.uuid4().hex[:12]}",
        k8s_namespace=namespace,
    )


@activity.defn
async def monitor_training(input: MonitorTrainingInput) -> MonitorOutput:
    # Deterministic one-shot status result for scaffold behavior.
    # In production this function polls Primus/K8s and heartbeat every 30s.
    while True:
        activity.RecordHeartbeat(
            {
                "auto_job_name": input.auto_job_name,
                "primus_job_id": input.primus_job_id,
                "k8s_namespace": input.k8s_namespace,
            }
        )
        if input.auto_job_name.startswith("kilvin-fail"):
            return MonitorOutput(final_status="FAILED", running_pods=0, total_pods=0)
        return MonitorOutput(final_status="SUCCESS", running_pods=1, total_pods=1)


@activity.defn
async def purge_resources(input: PurgeInput) -> bool:
    return True


@activity.defn
async def persist_yaml_artifact(input: ArtifactWriteInput) -> StepIOArtifact:
    """Persist an input or output payload for deterministic inspectability."""

    store = ArtifactStore(root_uri="file://./.kilvin-artifacts")
    artifact = store.write_yaml(
        input.run_id,
        input.run_attempt,
        input.artifact_name,
        input.payload,
    )
    return artifact


@activity.defn
async def submit_k8s_job_activity(input: SubmitK8sInput) -> SubmitK8sOutput:
    return await submit_k8s_job(input)
