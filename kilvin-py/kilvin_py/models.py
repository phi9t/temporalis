from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class JoinBehavior(str, Enum):
    ALL_REQUIRED = "all_required"
    ALL_OR_SKIP_FAILED = "all_or_skip_failed"
    FASTEST_SUCCESS = "fastest_success"
    ALLOW_PARTIAL = "allow_partial"


class PipelinePriority(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    PROBE = "probe"


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
    pipeline_id: str | None
    pipeline_index: int | None
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
    """Per-stage data requirements used by configure-training-data."""

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
class PipelineStrategy:
    mode: Literal["serial", "parallel"] = "parallel"
    max_parallelism: int | None = None
    join_behavior: JoinBehavior | str = JoinBehavior.ALL_REQUIRED

    def normalized_join_behavior(self) -> str:
        join_behavior = self.join_behavior
        if isinstance(join_behavior, JoinBehavior):
            if join_behavior == JoinBehavior.ALLOW_PARTIAL:
                return JoinBehavior.ALL_OR_SKIP_FAILED.value
            return join_behavior.value
        if join_behavior == "allow_partial":
            return JoinBehavior.ALL_OR_SKIP_FAILED.value
        return str(join_behavior)


@dataclass(frozen=True)
class PipelineConfig:
    pipeline_id: str
    component_name: str
    component_version: str = "latest"
    machine_type: str | None = None
    node_count: int = 1
    gpus_per_node: int = 1
    rank_size: int = 1
    resource_pool: str | None = None
    rdma_profile: str | None = None
    nccl_profile: str | None = None
    max_seq_len: int | None = None
    modality_mix: dict[str, float] | None = None
    transport_profile: str | None = None
    pipeline_type: str = "foundation_pretrain"
    skippable: bool = False
    priority: PipelinePriority | str = PipelinePriority.REQUIRED
    stage_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageConfig:
    stage_id: str
    stage_type: str
    phase: str
    enabled: bool
    dataset_profile: StageDatasetProfile
    runtime_profile: StageRuntimeProfile
    pipeline_strategy: PipelineStrategy | None = None
    pipelines: list[PipelineConfig] | None = None
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


@dataclass(frozen=True)
class ExtractStageConfigInput:
    run_id: str
    workflow_config_uri: str
    stage: StageConfig
    stage_index: int


@dataclass(frozen=True)
class ExtractStageConfigOutput:
    stage_id: str
    stage_index: int
    workflow_config_uri: str
    task_type: str
    pipeline_count: int
    pipeline_strategy_mode: str
    component_profile: dict[str, Any]
    resource_shape_hint: dict[str, int]


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
class CheckpointOutput:
    checkpoint_path: str
    manifest_uri: str
    model_size_estimate: int


@dataclass(frozen=True)
class ConfigureTrainingDataInput:
    dataset_uri: str
    dataset_stage: str
    required_token_budget: int
    min_examples: int | None
    token_budget_tolerance_ratio: float
    data_mix_requirements: dict[str, float] | None
    quality_thresholds: dict[str, float] | None


@dataclass(frozen=True)
class DataConfigureOutput:
    dataset_id: str
    schema_version: str
    shard_count: int
    estimated_tokens: int
    stage_token_mix: dict[str, int]
    composition_breakdown: dict[str, float]
    quality_scores: dict[str, float]
    total_examples: int
    format_ok: bool = True
    validation_report_path: str | None = None


@dataclass(frozen=True)
class AllocateResourcesInput:
    run_id: str
    stage_id: str
    stage_index: int
    pipeline_profiles: list[PipelineConfig]


@dataclass(frozen=True)
class PipelineAllocation:
    pipeline_id: str
    component_name: str
    node_count: int
    gpus_per_node: int
    rank_size: int
    machine_type: str
    pool_name: str
    rdma_enabled: bool = True
    nccl_profile: str = "nccl"
    rendezvous: dict[str, str] | None = None


@dataclass(frozen=True)
class ReamAllocationOutput:
    allocation_id: str
    resource_epoch: int
    pools_reservation_id: str
    pipeline_allocations: list[PipelineAllocation]


@dataclass(frozen=True)
class MaterializeWorkloadBundleInput:
    ir_name: str
    checkpoint: str
    config_snapshot: str
    pipeline_id: str
    allocation: PipelineAllocation
    pipeline_profile: PipelineConfig
    stage_index: int
    train_stage: str
    task_type: str
    total_tokens_target: int
    global_batch_tokens: int
    max_steps: int
    learning_rate: float
    model: str


MaterializeTrainingBundleInput = MaterializeWorkloadBundleInput


@dataclass(frozen=True)
class MaterializedBundleOutput:
    bundle_id: str
    bundle_path: str
    bound_components: list[dict[str, Any]]
    runtime_setup: dict[str, Any]
    rendezvous: dict[str, Any]
    launch_plan: list[dict[str, Any]]
    token_plan: dict[str, int]
    health_checks: list[str]


@dataclass(frozen=True)
class PipelineBundleOutput:
    pipeline_id: str
    bundle: MaterializedBundleOutput


@dataclass(frozen=True)
class SubmitK8sInput:
    pipeline_id: str
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
    pipeline_id: str
    auto_job_name: str
    primus_job_id: str
    ir_name: str
    k8s_namespace: str


@dataclass(frozen=True)
class MonitorOutput:
    final_status: str
    running_pods: int = 0
    total_pods: int = 0


@dataclass(frozen=True)
class PurgeInput:
    run_id: str
    stage_id: str
    preserve_artifacts: bool
    checkpoint: str | None = None


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
    pipeline_id: str | None
    step_name: str
    when: str = "pre"


@dataclass(frozen=True)
class ReplaySignal:
    scope: Literal["step", "pipeline", "stage"]
    target_stage_id: str
    target_pipeline_id: str | None
    target_step: str
    force: bool = False
    allow_dry_run: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class StageExecutionFailure:
    stage_id: str
    pipeline_id: str | None
    step_name: str
    attempt: int
    error: str


@dataclass(frozen=True)
class KilvinRunState:
    run_id: str
    run_attempt: int
    current_stage: str
    current_pipeline: str | None
    current_step: str | None
    overall_status: str
    paused: bool
    stage_traces: list[StepExecutionEnvelope]
    failures: list[StageExecutionFailure]
