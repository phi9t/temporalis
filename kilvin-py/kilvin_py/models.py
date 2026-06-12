from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class StepIOArtifact:
    """Content-addressed artifact reference produced by YAML persistence."""

    uri: str
    format: Literal["yaml"]
    checksum_sha256: str
    size_bytes: int


@dataclass(frozen=True)
class StepExecutionEnvelope:
    """One durable, inspectable record for a workflow step."""

    run_id: str
    run_attempt: int
    stage_id: str
    stage_index: int
    step_name: str
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED", "PAUSED"]
    retry_attempt: int
    input_artifact: StepIOArtifact
    output_artifact: StepIOArtifact | None = None
    error: str | None = None
    input_checksum: str = ""
    output_checksum: str | None = None
    command: str | None = None
    started_at_ms: int | None = None
    completed_at_ms: int | None = None


@dataclass(frozen=True)
class StageDatasetProfile:
    """Per-stage data requirements used for data-locality placement."""

    uri: str
    min_examples: int
    token_budget: int
    token_budget_tolerance_ratio: float = 0.0
    mix_requirements: dict[str, float] | None = None
    quality_thresholds: dict[str, float] | None = None


@dataclass(frozen=True)
class StageRuntimeProfile:
    total_tokens_target: int
    max_steps: int
    global_batch_tokens: int
    learning_rate: float
    optimizer: str = "adamw"
    precision: str = "bf16"


@dataclass(frozen=True)
class StageConfig:
    stage_id: str
    stage_type: str
    phase: str
    enabled: bool
    dataset_profile: StageDatasetProfile
    runtime_profile: StageRuntimeProfile
    stage_retry: int | None = None
    stage_timeout_minutes: int | None = None
    depends_on: list[str] | None = None


@dataclass(frozen=True)
class RunPolicy:
    max_stage_retries: int = 2
    stage_timeout_minutes: int = 1440
    purge_on_success: bool = True
    preserve_artifacts_on_failure: bool = True
    pause_on_step_failure: bool = True
    max_step_replay_attempts: int = 3
    artifact_store_uri: str = "file://./.kilvin-artifacts"


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    kilvin_run_name: str
    workflow_spec: str
    policy: RunPolicy
    stage_sequence: list[str]
    stages: list[StageConfig]
    metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class InterpretIntentInput:
    """The researcher's intent plus where to find run parameters."""

    run_config: RunConfig
    job_params_uri: str


@dataclass(frozen=True)
class TrainingIntent:
    """The interpreted intent: what to train, with which image and resources."""

    model_output_tos_key: str
    workflow_config_uri: str
    checkpoint: str | None
    stage_index: int
    component_profile: dict[str, Any]
    image_ref: str = ""
    trainer_env: dict[str, str] | None = None
    cpus: int = 2
    memory_gb: int = 4


@dataclass(frozen=True)
class TrainingWorkflowInput:
    run_id: str
    run_config: RunConfig
    job_params_uri: str = ""


@dataclass(frozen=True)
class ConcretizeDependenciesInput:
    run_id: str
    checkpoint: str | None
    image_ref: str = ""


@dataclass(frozen=True)
class ConcretizeDependenciesOutput:
    image_ref: str
    image_digest: str
    lockfile_sha256: str


@dataclass(frozen=True)
class AllocateResourcesInput:
    """Reserve real CPU/memory capacity from the allocator for one stage."""

    run_id: str
    stage_id: str
    stage_index: int
    dataset_uri: str
    cpus: int = 2
    memory_gb: int = 4


@dataclass(frozen=True)
class QuotaDecision:
    """Why this placement was granted: capacity at decision time, on which cluster."""

    cluster: str
    cpus_requested: int
    cpus_granted: int
    memory_gb_requested: int
    memory_gb_granted: int
    cpus_available_before: int
    memory_gb_available_before: int
    reason: str


@dataclass(frozen=True)
class ResourceAllocationOutput:
    """The allocator's grant: a real reservation against the finite ledger."""

    allocation_id: str
    cluster: str
    cpus: int
    memory_gb: int
    dataset_mount: str | None = None
    quota_decision: QuotaDecision | None = None


@dataclass(frozen=True)
class MaterializeTrainingBundleInput:
    ir_name: str
    checkpoint: str
    config_snapshot: str
    allocation: ResourceAllocationOutput
    stage_index: int
    train_stage: str
    task_type: str
    image_ref: str
    trainer_env: dict[str, str]
    model: str
    run_id: str = ""
    namespace: str = "kilvin-training"


@dataclass(frozen=True)
class MaterializedBundleOutput:
    bundle_id: str
    bundle_path: str
    job_manifest: dict[str, Any]
    env_vars: dict[str, str]
    launch_plan: list[dict[str, Any]]
    health_checks: list[str]


@dataclass(frozen=True)
class SubmitK8sInput:
    stage_id: str
    bundle: MaterializedBundleOutput
    namespace: str


@dataclass(frozen=True)
class SubmitK8sOutput:
    job_name: str
    job_uid: str
    k8s_namespace: str


@dataclass(frozen=True)
class MonitorTrainingInput:
    job_name: str
    job_uid: str
    ir_name: str
    k8s_namespace: str
    allocation_id: str = ""


@dataclass(frozen=True)
class MonitorOutput:
    final_status: str
    running_pods: int = 0
    total_pods: int = 0
    logs_uri: str = ""
    log_tail: list[str] | None = None


@dataclass(frozen=True)
class ArtifactWriteInput:
    run_id: str
    run_attempt: int
    artifact_name: str
    payload: Any


@dataclass(frozen=True)
class PauseSignal:
    reason: str | None = None


@dataclass(frozen=True)
class ResumeSignal:
    reason: str | None = None


@dataclass(frozen=True)
class CancelSignal:
    reason: str | None = None


@dataclass(frozen=True)
class PauseAtStepSignal:
    stage_id: str
    step_name: str
    when: str = "pre"


@dataclass(frozen=True)
class ReplaySignal:
    scope: Literal["step", "stage"]
    target_stage_id: str
    target_step: str
    force: bool = False
    allow_dry_run: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class StageExecutionFailure:
    stage_id: str
    step_name: str
    attempt: int
    error: str


@dataclass(frozen=True)
class KilvinRunState:
    run_id: str
    run_attempt: int
    current_stage: str
    current_step: str | None
    overall_status: str
    paused: bool
    stage_traces: list[StepExecutionEnvelope]
    failures: list[StageExecutionFailure]
