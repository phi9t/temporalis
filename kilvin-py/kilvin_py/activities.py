from __future__ import annotations

import asyncio
import hashlib
import os
import socket
import uuid

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .allocator_client import AllocatorClient, AllocatorUnavailable, QuotaExhausted
from .artifacts import ArtifactStore
from .config import KilvinSettings
from .k8s_jobs import KubeconfigMissing, KubernetesJobs
from .k8s_manifest import render_job_manifest
from .models import (
    AllocateResourcesInput,
    ArtifactWriteInput,
    ConcretizeDependenciesInput,
    ConcretizeDependenciesOutput,
    InterpretIntentInput,
    MaterializedBundleOutput,
    MaterializeTrainingBundleInput,
    MonitorOutput,
    MonitorTrainingInput,
    QuotaDecision,
    ResourceAllocationOutput,
    SubmitK8sInput,
    SubmitK8sOutput,
    StepIOArtifact,
    TrainingIntent,
)
from .proc import SubprocessFailed, run_logged

# Two-scale mapping: the intent is production-shaped (FineWeb, 64 A100s); the
# local materialization trains a tiny CPU GPT-2 with the same workflow.
LAPTOP_TRAINER_DEFAULTS = {
    "N_LAYER": "4",
    "N_HEAD": "4",
    "N_EMBD": "128",
    "BLOCK_SIZE": "128",
    "BATCH_SIZE": "8",
    "LEARNING_RATE": "0.0003",
    "SEED": "1337",
    "LOG_EVERY": "10",
    "DATA_PATH": "/app/data/input.txt",
    "OUT_DIR": "/output",
}
LAPTOP_MAX_STEPS = 200
MONITOR_POLL_SECONDS = 5
DOCKER_BUILD_HOSTS = (
    "files.pythonhosted.org",
    "download.pytorch.org",
    "download-r2.pytorch.org",
    "pypi.org",
)
LAPTOP_TRAINER_ENV_OVERRIDES = {
    "N_LAYER": "KILVIN_LAPTOP_N_LAYER",
    "N_HEAD": "KILVIN_LAPTOP_N_HEAD",
    "N_EMBD": "KILVIN_LAPTOP_N_EMBD",
    "BLOCK_SIZE": "KILVIN_LAPTOP_BLOCK_SIZE",
    "BATCH_SIZE": "KILVIN_LAPTOP_BATCH_SIZE",
    "LOG_EVERY": "KILVIN_LAPTOP_LOG_EVERY",
}


def laptop_max_steps() -> int:
    return int(os.environ.get("KILVIN_LAPTOP_MAX_STEPS", str(LAPTOP_MAX_STEPS)))


def laptop_trainer_defaults() -> dict[str, str]:
    defaults = dict(LAPTOP_TRAINER_DEFAULTS)
    for trainer_key, env_key in LAPTOP_TRAINER_ENV_OVERRIDES.items():
        if env_key in os.environ:
            defaults[trainer_key] = os.environ[env_key]
    return defaults


def docker_build_command(image_ref: str) -> list[str]:
    """Build command with host-resolved package domains for Colima DNS failures."""

    command = ["docker", "build"]
    for host in DOCKER_BUILD_HOSTS:
        try:
            address = socket.gethostbyname(host)
        except OSError:
            continue
        command.extend(["--add-host", f"{host}:{address}"])
    command.extend(["-t", image_ref, "."])
    return command


@activity.defn
async def interpret_training_intent(input: InterpretIntentInput) -> TrainingIntent:
    """Turn the researcher's intent into the typed plan the workflow executes."""

    settings = KilvinSettings.load()
    run_config = input.run_config
    run_stages = run_config.stages
    stage = run_stages[0]
    stage_zero_dataset = stage.dataset_profile.uri if run_stages else "hdfs://datasets/fineweb"

    trainer_env = laptop_trainer_defaults()
    trainer_env.update(
        {
            "RUN_ID": run_config.run_id,
            "MODEL_NAME": "model-x",
            "TRAIN_STAGE": stage.stage_id,
            "MAX_STEPS": str(min(stage.runtime_profile.max_steps, laptop_max_steps())),
        }
    )

    return TrainingIntent(
        model_output_tos_key=input.job_params_uri,
        workflow_config_uri=f"file://./.kilvin-cache/{run_config.run_id}/workflow.yaml",
        checkpoint="s3://checkpoints/model-x/base",
        stage_index=0,
        component_profile={
            "run_name": run_config.kilvin_run_name,
            "model": "model-x",
            "dataset_root": stage_zero_dataset,
            "spec_version": run_config.workflow_spec,
        },
        image_ref=f"{settings.registry}/kilvin-trainer:{run_config.run_id}",
        trainer_env=trainer_env,
        cpus=2,
        memory_gb=4,
    )


@activity.defn
async def concretize_dependencies(
    input: ConcretizeDependenciesInput,
) -> ConcretizeDependenciesOutput:
    """Build the training image and pin dependencies into a concrete code bundle."""

    settings = KilvinSettings.load()
    trainer_dir = settings.trainer_dir
    lockfile = trainer_dir / "uv.lock"
    if not lockfile.exists():
        raise ApplicationError(
            f"trainer lockfile missing at {lockfile}; run `uv lock` in {trainer_dir}",
            non_retryable=True,
        )

    try:
        await run_logged(["uv", "lock", "--check"], cwd=trainer_dir, label="uv-lock-check")
        await run_logged(
            docker_build_command(input.image_ref),
            cwd=trainer_dir,
            label="docker-build",
        )
        await run_logged(["docker", "push", input.image_ref], cwd=trainer_dir, label="docker-push")
        inspect = await run_logged(
            ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", input.image_ref],
            label="docker-inspect",
        )
    except SubprocessFailed as err:
        raise ApplicationError(str(err), type="BuildFailed") from err

    repo_digest = inspect[-1].strip()
    if "@sha256:" not in repo_digest:
        raise ApplicationError(
            f"could not resolve image digest from {repo_digest!r}",
            type="BuildFailed",
        )
    digest = repo_digest.split("@", 1)[1]

    return ConcretizeDependenciesOutput(
        image_ref=input.image_ref,
        image_digest=digest,
        lockfile_sha256=hashlib.sha256(lockfile.read_bytes()).hexdigest(),
    )


@activity.defn
async def allocate_resources(input: AllocateResourcesInput) -> ResourceAllocationOutput:
    """Gather quota/placement constraints, solve placement, and reserve resources."""

    settings = KilvinSettings.load()
    client = AllocatorClient(settings.allocator_url)
    try:
        grant = await client.request_allocation(
            run_id=input.run_id,
            stage_id=input.stage_id,
            cpus=input.cpus,
            memory_gb=input.memory_gb,
        )
    except QuotaExhausted as err:
        raise ApplicationError(str(err), type="QuotaExhausted") from err
    except AllocatorUnavailable as err:
        raise ApplicationError(str(err), non_retryable=True) from err

    return ResourceAllocationOutput(
        allocation_id=grant.allocation_id,
        cluster=grant.cluster,
        cpus=grant.cpus_granted,
        memory_gb=grant.memory_gb_granted,
        dataset_mount=input.dataset_uri,
        quota_decision=QuotaDecision(**grant.quota_decision),
    )


@activity.defn
async def materialize_training_bundle(
    input: MaterializeTrainingBundleInput,
) -> MaterializedBundleOutput:
    """Expand training intent into the concrete launch spec for this stage."""

    job_name = f"kilvin-{input.train_stage}-{uuid.uuid4().hex[:6]}"
    env_vars = dict(input.trainer_env)
    env_vars.setdefault("CHECKPOINT_URI", input.checkpoint)
    env_vars.setdefault("DATASET_MOUNT", input.allocation.dataset_mount or "")

    manifest = render_job_manifest(
        job_name=job_name,
        namespace=input.namespace,
        image=input.image_ref,
        env=env_vars,
        cpus=input.allocation.cpus,
        memory_gb=input.allocation.memory_gb,
        run_id=input.run_id,
        stage_id=input.train_stage,
    )

    return MaterializedBundleOutput(
        bundle_id=f"bundle-{uuid.uuid4().hex[:10]}",
        bundle_path=f"{input.config_snapshot}/bundle/{input.train_stage}.yaml",
        job_manifest=manifest,
        env_vars=env_vars,
        launch_plan=[{"entrypoint": "python trainer.py", "image": input.image_ref}],
        health_checks=["job-conditions", "pod-logs"],
    )


@activity.defn
async def submit_k8s_job(input: SubmitK8sInput) -> SubmitK8sOutput:
    """Create the rendered Job on the k3s cluster."""

    settings = KilvinSettings.load()
    try:
        jobs = KubernetesJobs(settings.kubeconfig_path)
        name, uid = await asyncio.to_thread(jobs.create_job, input.bundle.job_manifest)
    except KubeconfigMissing as err:
        raise ApplicationError(str(err), non_retryable=True) from err
    return SubmitK8sOutput(job_name=name, job_uid=uid, k8s_namespace=input.namespace)


@activity.defn
async def monitor_training(input: MonitorTrainingInput) -> MonitorOutput:
    """Watch the Job until completion, heartbeating; release the allocation."""

    settings = KilvinSettings.load()
    try:
        jobs = KubernetesJobs(settings.kubeconfig_path)
    except KubeconfigMissing as err:
        raise ApplicationError(str(err), non_retryable=True) from err

    status = "RUNNING"
    while status == "RUNNING":
        status = await asyncio.to_thread(jobs.job_status, input.job_name, input.k8s_namespace)
        activity.heartbeat(
            {
                "job_name": input.job_name,
                "namespace": input.k8s_namespace,
                "status": status,
            }
        )
        if status == "RUNNING":
            await asyncio.sleep(MONITOR_POLL_SECONDS)

    log_tail = await asyncio.to_thread(jobs.pod_log_tail, input.job_name, input.k8s_namespace, 40)

    if input.allocation_id and not input.allocation_id.startswith("skip-"):
        try:
            await AllocatorClient(settings.allocator_url).release(input.allocation_id)
        except AllocatorUnavailable:
            pass

    logs_uri = f"k8s://{input.k8s_namespace}/jobs/{input.job_name}/logs"
    return MonitorOutput(
        final_status="SUCCESS" if status == "SUCCEEDED" else "FAILED",
        running_pods=0,
        total_pods=1,
        logs_uri=logs_uri,
        log_tail=log_tail,
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
