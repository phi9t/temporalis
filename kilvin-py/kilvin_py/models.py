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
class StartKilvinCommandInput:
    run_config: RunConfig
    cmd_name: str
    job_params_uri: str


@dataclass(frozen=True)
class ParentRunOutput:
    run_id: str
    final_state: str
    ir_name: str | None
    error: str | None = None


@dataclass(frozen=True)
class ExtractWorkflowConfigInput:
    run_config: RunConfig
    cmd_name: str
    job_params_uri: str


@dataclass(frozen=True)
class ExtractWorkflowConfigOutput:
    model_output_tos_key: str
    workflow_config_uri: str
    checkpoint: str | None
    stage_index: int
    component_profile: dict[str, Any]


ExtractCmdConfigInput = ExtractWorkflowConfigInput
ExtractCmdConfigOutput = ExtractWorkflowConfigOutput


@dataclass(frozen=True)
class TrainingWorkflowInput:
    run_id: str
    run_config: RunConfig
    extracted: ExtractWorkflowConfigOutput


@dataclass(frozen=True)
class DevPrepareInput:
    run_id: str
    checkpoint: str | None


@dataclass(frozen=True)
class DevPrepareOutput:
    auto_job_id: str
    code_tos_key: str


@dataclass(frozen=True)
class AllocateResourcesInput:
    """Gather quota/placement constraints and reserve resources for one stage."""

    run_id: str
    stage_id: str
    stage_index: int
    dataset_uri: str
    node_count: int = 8
    gpus_per_node: int = 8
    machine_type: str = "a100-sxm"
    resource_pool: str = "foundation"


@dataclass(frozen=True)
class QuotaDecision:
    """Why this placement was selected: cluster, racks, node pool, and data locality."""

    cluster: str
    racks: list[str]
    node_pool: str
    gpus_requested: int
    gpus_granted: int
    data_locality: str
    reason: str


@dataclass(frozen=True)
class ReamAllocationOutput:
    """The placement decision: cluster, pool, machines, and data locality."""

    allocation_id: str
    resource_epoch: int
    pools_reservation_id: str
    machine_type: str
    pool_name: str
    node_count: int
    gpus_per_node: int
    rank_size: int
    rdma_enabled: bool = True
    nccl_profile: str = "nccl"
    rendezvous: dict[str, str] | None = None
    dataset_mount: str | None = None
    quota_decision: QuotaDecision | None = None


@dataclass(frozen=True)
class MaterializeTrainingBundleInput:
    ir_name: str
    checkpoint: str
    config_snapshot: str
    allocation: ReamAllocationOutput
    stage_index: int
    train_stage: str
    task_type: str
    total_tokens_target: int
    global_batch_tokens: int
    max_steps: int
    learning_rate: float
    model: str


@dataclass(frozen=True)
class MaterializedBundleOutput:
    bundle_id: str
    bundle_path: str
    bound_components: list[dict[str, Any]]
    runtime_setup: dict[str, Any]
    env_vars: dict[str, str]
    rendezvous: dict[str, Any]
    launch_plan: list[dict[str, Any]]
    token_plan: dict[str, int]
    health_checks: list[str]


@dataclass(frozen=True)
class SubmitK8sInput:
    stage_id: str
    bundle: MaterializedBundleOutput
    namespace: str


@dataclass(frozen=True)
class SubmitK8sOutput:
    auto_job_name: str
    primus_job_id: str
    primus_ui_url: str
    k8s_namespace: str


@dataclass(frozen=True)
class MonitorTrainingInput:
    auto_job_name: str
    primus_job_id: str
    ir_name: str
    k8s_namespace: str


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
