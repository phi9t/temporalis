from __future__ import annotations

import uuid

from temporalio import activity

from .artifacts import ArtifactStore
from .models import (
    AllocateResourcesInput,
    ArtifactWriteInput,
    DevPrepareInput,
    DevPrepareOutput,
    ExtractWorkflowConfigInput,
    ExtractWorkflowConfigOutput,
    MaterializedBundleOutput,
    MaterializeTrainingBundleInput,
    MonitorOutput,
    MonitorTrainingInput,
    QuotaDecision,
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
    stage_zero_dataset = run_stages[0].dataset_profile.uri if run_stages else "hdfs://datasets/fineweb"
    stage_zero_checkpoint = run_stages[0].dataset_profile.uri if run_stages else "s3://checkpoints/model-x"

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


extract_cmd_config = extract_workflow_config


@activity.defn
async def dev_prepare(input: DevPrepareInput) -> DevPrepareOutput:
    """Build the training image and sync dependencies for the run."""

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
async def allocate_resources(input: AllocateResourcesInput) -> ReamAllocationOutput:
    """Gather quota/placement constraints, solve placement, and reserve resources."""

    gpus_requested = input.node_count * input.gpus_per_node
    quota_decision = QuotaDecision(
        cluster="us-east-train-7",
        racks=["rack-a3", "rack-b1"],
        node_pool=f"{input.machine_type}-{gpus_requested}",
        gpus_requested=gpus_requested,
        gpus_granted=gpus_requested,
        data_locality=f"{input.dataset_uri} available on cluster-local storage",
        reason=(
            f"{input.node_count}x{input.gpus_per_node} {input.machine_type} fit on two healthy "
            "racks with RDMA networking and dataset-local storage"
        ),
    )
    return ReamAllocationOutput(
        allocation_id=f"alloc-{uuid.uuid4().hex[:10]}",
        resource_epoch=1,
        pools_reservation_id=f"pool-{uuid.uuid4().hex[:8]}",
        machine_type=input.machine_type,
        pool_name=input.resource_pool,
        node_count=input.node_count,
        gpus_per_node=input.gpus_per_node,
        rank_size=gpus_requested,
        rdma_enabled=True,
        nccl_profile="nccl",
        rendezvous={"control": "grpc://kilvin-controller:9001"},
        dataset_mount=f"{input.dataset_uri}/mounts/{input.stage_id}",
        quota_decision=quota_decision,
    )


@activity.defn
async def materialize_training_bundle(
    input: MaterializeTrainingBundleInput,
) -> MaterializedBundleOutput:
    """Expand training intent into the concrete launch spec for this stage."""

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
        "nccl_profile": input.allocation.nccl_profile,
        "rdma_enabled": input.allocation.rdma_enabled,
        "dataset_mount": input.allocation.dataset_mount,
    }

    bound_components = [
        {
            "component": input.model,
            "machine_type": input.allocation.machine_type,
            "node_count": input.allocation.node_count,
            "gpus_per_node": input.allocation.gpus_per_node,
        }
    ]

    env_vars = {
        "MODEL_NAME": input.model,
        "TRAIN_STAGE": input.train_stage,
        "CHECKPOINT_URI": input.checkpoint,
        "DATASET_MOUNT": input.allocation.dataset_mount or "",
        "WORLD_SIZE": str(input.allocation.rank_size),
        "NCCL_PROFILE": input.allocation.nccl_profile,
        "RDMA_ENABLED": "1" if input.allocation.rdma_enabled else "0",
        "GLOBAL_BATCH_TOKENS": str(input.global_batch_tokens),
        "LEARNING_RATE": str(input.learning_rate),
    }

    return MaterializedBundleOutput(
        bundle_id=f"bundle-{uuid.uuid4().hex[:10]}",
        bundle_path=f"{input.config_snapshot}/bundle/{input.train_stage}.yaml",
        bound_components=bound_components,
        runtime_setup=runtime_setup,
        env_vars=env_vars,
        rendezvous=dict(input.allocation.rendezvous or {}),
        launch_plan=[
            {
                "entrypoint": "kilvin-train",
                "args": ["--config", input.config_snapshot, "--stage", input.train_stage],
            }
        ],
        token_plan=launch_budget,
        health_checks=["nccl-rings", "kv-router", "data-loader", "rdma-topology"],
    )


@activity.defn
async def submit_k8s_job(input: SubmitK8sInput) -> SubmitK8sOutput:
    namespace = input.namespace or "kilvin-training"
    return SubmitK8sOutput(
        auto_job_name=f"kilvin-{input.stage_id}-{uuid.uuid4().hex[:6]}",
        primus_job_id=f"p-{uuid.uuid4().hex[:12]}",
        primus_ui_url=f"https://primus.local/kilvin/{uuid.uuid4().hex[:12]}",
        k8s_namespace=namespace,
    )


@activity.defn
async def monitor_training(input: MonitorTrainingInput) -> MonitorOutput:
    # Deterministic one-shot status result for scaffold behavior.
    # In production this function polls Primus/K8s and heartbeats every 30s.
    activity.heartbeat(
        {
            "auto_job_name": input.auto_job_name,
            "primus_job_id": input.primus_job_id,
            "k8s_namespace": input.k8s_namespace,
        }
    )
    logs_uri = f"k8s://{input.k8s_namespace}/jobs/{input.auto_job_name}/logs"
    if input.auto_job_name.startswith("kilvin-fail"):
        return MonitorOutput(
            final_status="FAILED",
            running_pods=0,
            total_pods=0,
            logs_uri=logs_uri,
            log_tail=[f"{input.auto_job_name}: pod crash-looped, see {logs_uri}"],
        )
    return MonitorOutput(
        final_status="SUCCESS",
        running_pods=1,
        total_pods=1,
        logs_uri=logs_uri,
        log_tail=[
            f"{input.auto_job_name}: all pods Running",
            f"{input.auto_job_name}: training loop healthy, checkpoints flowing",
        ],
    )


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
