# Kilvin Temporal Training Framework Design (v0)

## Goal
Build **kilvin** from scratch as a Temporal-native training orchestration framework, replacing the legacy hand-rolled workflow model with a deterministic, durable, typed workflow engine. The framework is intentionally language-first by SDK and includes parallel implementations in **Python** and **Go** that share the same design principles but use each language’s idioms.

Kilvin is grounded first in foundation-model training: pretraining (including multimodal and long-context tracks) is the primary business objective, with optional stages (CPT/SFT/PARL/QAT) modeled as extension stages layered after the base run.

## Naming Rationale
`kilvin` is inspired by Kelvin as a model for reliable, high-precision engineering: durable workflows that behave like an absolute baseline. It also nods to Master Kilvin’s steady, logic-heavy craftsmanship from the Kingkiller Chronicle, a fitting metaphor for dependable long-running pipelines.

## Scope

This design covers:

- New `kilvin` workflows and activities that cover the full training run path (`extract_workflow_config -> extract_stage_config -> validate_checkpoint -> configure_training_data -> allocate_resources -> materialize_workload_bundle -> submit_k8s_job -> monitor_training -> purge_resources`).
- A parent command workflow that launches a child training workflow.
- Typed inter-step contracts (no JSON blobs) and durable run state in Temporal history.
- Heartbeating long-running monitoring activity.
- Signals/queries for pause/resume/status.

This design does not include:

- A compatibility layer for existing control-plane orchestrators.
- Support for other Durable Execution engines.
- Full UI implementation (CLI/TUI comes later).

## Shared Design Principles (Both Languages)

### 1) Domain naming and boundaries
Rename conceptual entities from legacy terminology to **kilvin**:

- `cmd` -> `run` or `kilvin_run`
- `ir_job` -> `kilvin_job`
- `job_stages` -> `kilvin_stages`
- `store_outputs()` -> typed return values (`Output` structs/models)
- `workflow_dag` -> explicit language-native workflow function calls

### 1b) Artifact and config serialization

All run definitions, stage plans, and step IO artifacts are serialized in YAML when stored for inspection or replay.

- `RunConfig` and runtime plans are defined in YAML and treated as canonical for plan hashing.
- Step input/output artifacts are serialized to canonical YAML with stable key ordering.
- `StepExecutionEnvelope` points to artifact URIs and their YAML checksums; JSON is only permitted inside internal runtime transport where required.

### 2) One parent + one child workflow flow
The parent workflow is responsible for run extraction and terminal state updates; the child workflow executes the training stage sequence. No custom DB row coordination.

### 3) Typed contracts everywhere
Every boundary between steps passes typed input/output models:

- Stage extract output
- Checkpoint validation output
- Data readiness output (as `configure_training_data` output)
- REAM allocation output
- K8s submit output
- Monitoring output

No schema-less JSON blobs in control flow.

### 4) Retry and failure are explicit, declarative
Use SDK-native retry at activity level and child-workflow level. Keep retry policy centralized near orchestration, not scattered custom loops.

### 5) Long-running monitor = heartbeating activity
The monitor is a single durable activity that heartbeats its last poll position and returns terminal status/failure deterministically.

### 6) No scheduler polling loops
No `job_scheduler`, `stage_scheduler`, `task_scheduler`, or manual rescheduler loops are part of kilvin.

### 7) Foundation-first stage semantics
Default `kilvin` runs always execute foundation stages first. Optional stages can be appended or removed by run config, but the base objective remains foundation-model convergence.

Default foundation sequence:
1. `vit_pretrain`
2. `joint_pretrain`
3. `continue_pretrain`
4. `long_context_midtrain`

Optional extension stages:
- `cpt`
- `sft`
- `parl_rl`
- `agentic_synthesis`
- `qat`

### Run configuration contract (typed baseline)

The stage graph is fully declared in `RunConfig` and validated before stage execution begins. `RunConfig` is the single source of truth for ordering, defaults, dependencies, and cost-control policy.

#### Core schema

```yaml
run_id: string
kilvin_run_name: string
workflow_spec: string
policy:
  max_stage_retries: 2
  stage_timeout_minutes: 1440
  purge_on_success: true
  preserve_artifacts_on_failure: true
  pause_on_step_failure: true
  artifact_store_uri: s3://kilvin-artifacts/runs
  max_step_replay_attempts: 3
stage_sequence:
  - vit_pretrain
  - joint_pretrain
  - continue_pretrain
  - long_context_midtrain
  - cpt
  - sft
  - parl_rl
  - agentic_synthesis
  - qat
stages:
  - stage_id: vit_pretrain
    stage_type: pretrain
    phase: foundation
    enabled: true
    dataset_profile:
      uri: hdfs://.../vit_pretrain
      min_examples: 50000000
      token_budget: 1000000000000
      token_budget_tolerance_ratio: 0.05
      mix_requirements:
        visual: 0.7
        text: 0.3
    runtime_profile:
      total_tokens_target: 1000000000000
      max_steps: 120000
      global_batch_tokens: 262144
      learning_rate: 1.5e-4
    pipeline_strategy:
      mode: parallel
      max_parallelism: 4
      join_behavior: all_required
    pipelines:
      - pipeline_id: vit_encoder
        component_name: moonvit3d
        machine_type: h100-sxm
        resource_pool: vision-ndv4
        node_count: 128
        gpus_per_node: 8
        rank_size: 1024
        rdma_profile: ib-h100
        nccl_profile: nccl-ib
        max_seq_len: 8192
        modality_mix:
          visual: 1.0
      - pipeline_id: vit_auxiliary
        component_name: navi_pack
        resource_pool: vision-aux
        machine_type: h100-sxm
        node_count: 64
        gpus_per_node: 8
        rank_size: 512
        rdma_profile: ib-h100
        nccl_profile: nccl-ib
        max_seq_len: 4096
        modality_mix:
          visual: 0.5
          text: 0.5
        runtime_overrides:
          global_batch_tokens: 131072
    stage_retry: 2
    stage_timeout_minutes: 1440
    depends_on: []
```

#### RunConfig validation rules

1. `stage_sequence` must be deterministic and match enabled `stages` order in execution form.
2. Foundation phases must be `vit_pretrain -> joint_pretrain -> continue_pretrain -> long_context_midtrain` for any enabled subset that preserves dependency integrity.
3. `stage_id` must be one of: `vit_pretrain`, `joint_pretrain`, `continue_pretrain`, `long_context_midtrain`, `cpt`, `sft`, `parl_rl`, `agentic_synthesis`, `qat`.
4. `phase` must be `foundation` for the first four and `post_foundation` for the rest.
5. Foundation stage `enabled=true` implies `depends_on` is empty unless dependency chaining is explicitly requested for advanced experiments.
6. Post-foundation stages MAY declare dependency on a specific predecessor but cannot execute without the latest checkpoint from the last completed stage.
7. `stage_retry` and `stage_timeout` may be set at stage level; missing values inherit `policy`.
8. `pipelines` is optional. If omitted, runtime creates a single implicit pipeline from stage defaults.
9. When `pipeline_strategy.mode="parallel"`, pipelines are scheduled with bounded parallelism and joined at stage fan-in before transition.
10. `pipeline_strategy.max_parallelism` controls the maximum number of pipelines that execute concurrently; when unset, default is `len(pipelines)`.
11. `join_behavior` values:
   - `all_required`: stage fails if any pipeline fails.
   - `all_or_skip_failed` (optional): allows explicit skip policy for best-effort pipelines.
   - `fastest_success` (optional): returns as soon as one successful pipeline reaches terminal success, cancelling remaining pipelines.

#### Example profiles

Foundation-only run:

```yaml
run_id: run-001
stage_sequence:
  - vit_pretrain
  - joint_pretrain
  - continue_pretrain
  - long_context_midtrain
stages:
  - stage_id: vit_pretrain
    stage_type: pretrain
    phase: foundation
    enabled: true
  - stage_id: joint_pretrain
    stage_type: continued_pretrain
    phase: foundation
    enabled: true
  - stage_id: continue_pretrain
    stage_type: continued_pretrain
    phase: foundation
    enabled: true
  - stage_id: long_context_midtrain
    stage_type: pretrain
    phase: foundation
    enabled: true
```

Parallel pipeline example (single stage with concurrent vision sub-pipelines):

```yaml
run_id: run-vision-fanout
stage_sequence:
  - vit_pretrain
stages:
  - stage_id: vit_pretrain
    stage_type: pretrain
    phase: foundation
    enabled: true
    dataset_profile:
      uri: hdfs://dataspec/vit_pretrain/
      min_examples: 50000000
      token_budget: 1000000000000
      token_budget_tolerance_ratio: 0.05
      mix_requirements:
        visual: 1.0
    runtime_profile:
      total_tokens_target: 1000000000000
      max_steps: 120000
      global_batch_tokens: 262144
      learning_rate: 1.5e-4
    pipeline_strategy:
      mode: parallel
      max_parallelism: 2
      join_behavior: all_required
    pipelines:
      - pipeline_id: vision-primary
        component_name: moonvit3d-main
        machine_type: h100-sxm
        resource_pool: vision-large
        node_count: 128
        gpus_per_node: 8
        rank_size: 1024
        rdma_profile: ib-h100
        nccl_profile: nccl
        max_seq_len: 8192
        modality_mix:
          visual: 1.0
      - pipeline_id: vision-aux
        component_name: vision-pack-prep
        machine_type: h100-sxm
        resource_pool: vision-aux
        node_count: 64
        gpus_per_node: 8
        rank_size: 512
        rdma_profile: ib-h100
        nccl_profile: nccl
        max_seq_len: 4096
        modality_mix:
          visual: 0.7
          text: 0.3
    stage_retry: 2
    stage_timeout_minutes: 1440
    depends_on: []
```

A-la-carte with extensions:

```yaml
run_id: run-002
stage_sequence:
  - vit_pretrain
  - joint_pretrain
  - continue_pretrain
  - long_context_midtrain
  - sft
  - qat
stages:
  - stage_id: vit_pretrain
    stage_type: pretrain
    phase: foundation
    enabled: true
  - stage_id: joint_pretrain
    stage_type: continued_pretrain
    phase: foundation
    enabled: true
  - stage_id: continue_pretrain
    stage_type: continued_pretrain
    phase: foundation
    enabled: true
  - stage_id: long_context_midtrain
    stage_type: pretrain
    phase: foundation
    enabled: true
  - stage_id: sft
    stage_type: fine_tune
    phase: post_foundation
    enabled: true
    depends_on:
      - long_context_midtrain
  - stage_id: qat
    stage_type: post_train
    phase: post_foundation
    enabled: true
    depends_on:
      - sft
```

#### Python contract sketch

```python
@dataclass(frozen=True)
class RunConfig:
    run_id: str
    kilvin_run_name: str
    workflow_spec: str
    policy: "RunPolicy"
    stage_sequence: list[str]
    stages: list["StageConfig"]


@dataclass(frozen=True)
class StageDatasetProfile:
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
    mode: str = "parallel"  # serial | parallel
    max_parallelism: int = 1
    join_behavior: str = "all_required"  # all_required | all_or_skip_failed | fastest_success


@dataclass(frozen=True)
class PipelineConfig:
    pipeline_id: str
    component_name: str
    machine_type: str
    node_count: int
    gpus_per_node: int
    rank_size: int
    resource_pool: str | None = None
    rdma_profile: str | None = None
    nccl_profile: str | None = None
    max_seq_len: int | None = None
    modality_mix: dict[str, float] | None = None
    token_budget: int | None = None
    runtime_overrides: StageRuntimeProfile | dict[str, int] | None = None


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
    max_stage_retries: int
    stage_timeout_minutes: int
    purge_on_success: bool
    preserve_artifacts_on_failure: bool
    pause_on_step_failure: bool = True
    max_step_replay_attempts: int = 3
    artifact_store_uri: str | None = None
```

#### Go contract sketch

```go
type RunConfig struct {
    RunID          string        `json:"run_id"`
    RunName        string        `json:"kilvin_run_name"`
    WorkflowSpec   string        `json:"workflow_spec"`
    Policy         RunPolicy     `json:"policy"`
    StageSequence  []string      `json:"stage_sequence"`
    Stages         []StageConfig `json:"stages"`
}

type StageDatasetProfile struct {
    URI                      string             `json:"uri"`
    MinExamples              int                `json:"min_examples"`
    TokenBudget              int64              `json:"token_budget"`
    TokenBudgetTolerance     float64            `json:"token_budget_tolerance_ratio"`
    MixRequirements          map[string]float64  `json:"mix_requirements"`
    QualityThresholds        map[string]float64  `json:"quality_thresholds"`
}

type StageRuntimeProfile struct {
    TotalTokensTarget int64   `json:"total_tokens_target"`
    MaxSteps          int     `json:"max_steps"`
    GlobalBatchTokens int     `json:"global_batch_tokens"`
    LearningRate      float64 `json:"learning_rate"`
    Optimizer         string  `json:"optimizer"`
    Precision         string  `json:"precision"`
}

type PipelineStrategy struct {
    Mode            string `json:"mode"`             // serial | parallel
    MaxParallelism  int    `json:"max_parallelism"`
    JoinBehavior    string `json:"join_behavior"`    // all_required | all_or_skip_failed | fastest_success
}

type PipelineConfig struct {
    PipelineID      string             `json:"pipeline_id"`
    ComponentName   string             `json:"component_name"`
    MachineType     string             `json:"machine_type"`
    ResourcePool    string             `json:"resource_pool"`
    NodeCount       int                `json:"node_count"`
    GPUsPerNode     int                `json:"gpus_per_node"`
    RankSize        int                `json:"rank_size"`
    RDMAProfile     string             `json:"rdma_profile"`
    NCCLProfile     string             `json:"nccl_profile"`
    MaxSeqLen       int                `json:"max_seq_len"`
    ModalityMix     map[string]float64 `json:"modality_mix"`
    TokenBudget     int64              `json:"token_budget"`
    RuntimeOverrides map[string]int     `json:"runtime_overrides"`
}

type StageConfig struct {
    StageID             string              `json:"stage_id"`
    StageType           string              `json:"stage_type"`
    Phase               string              `json:"phase"`
    Enabled             bool                `json:"enabled"`
    DatasetProfile      StageDatasetProfile `json:"dataset_profile"`
    RuntimeProfile      StageRuntimeProfile `json:"runtime_profile"`
    PipelineStrategy    PipelineStrategy    `json:"pipeline_strategy"`
    Pipelines           []PipelineConfig    `json:"pipelines"`
    StageRetry          int                 `json:"stage_retry"`
    StageTimeoutMinutes int                 `json:"stage_timeout_minutes"`
    DependsOn           []string            `json:"depends_on"`
}

type RunPolicy struct {
    MaxStageRetries              int  `json:"max_stage_retries"`
    StageTimeoutMinutes          int  `json:"stage_timeout_minutes"`
    PurgeOnSuccess               bool `json:"purge_on_success"`
    PreserveArtifactsOnFailure    bool `json:"preserve_artifacts_on_failure"`
    PauseOnStepFailure           bool `json:"pause_on_step_failure"`
    MaxStepReplayAttempts        int  `json:"max_step_replay_attempts"`
    ArtifactStoreURI             string `json:"artifact_store_uri"`
}
```

## API Surface (Core, Shared)

Each language version should provide:

- `start_kilvin_command(...)` client call
- `RunConfig` input model
- `run status` query (workflow query handler)
- `run step trace` query (ordered list of step-level records)
- `run artifacts` query (filtered by stage/pipeline/step for inspection)
- `get run plan` query (resolved stage/pipeline/step execution graph)
- `pause`, `resume`, `cancel`, `pause_at_step`, `replay_step` signals

Core workflows:

- `ParentKilvinCmdWorkflow(input)`
- `KilvinTrainingWorkflow(input)`

Core activities:

- `extract_workflow_config`
- `extract_stage_config`
- `update_cmd_state`
- `dev_prepare`
- `validate_checkpoint`
- `configure_training_data`
- `allocate_resources`
- `materialize_workload_bundle`
  - Builds a fully materialized training bundle after resource allocation:
    - selected training components and their machine-type bindings
    - pipeline-specific topology, rank maps, and resource pool assignments
    - networking/runtime envelope (RDMA/NCCL, fabric placement, env/launch plans)
    - token/optimizer/runtime knobs attached to concrete resources.
- `submit_k8s_job`
  - Receives `pipeline_id` context when multiple pipelines are active.
- `monitor_training`
- `RunPipeline` (logical helper workflow/activity in workflow-level orchestration for each pipeline)
- `purge_resources`

### Step-level execution ledger (required)

Inspection and replay are first-class: every step execution must emit an immutable record plus explicit input/output artifacts.

- Each step writes:
  - `StepIOArtifact` for input (serialized canonical form)
  - `StepIOArtifact` for output (serialized canonical form, if produced)
  - `StepExecutionEnvelope` metadata
- Artifacts are written under the run root and are read-only after write.
- The envelope references:
  - `run_id`, `run_attempt`
  - `stage_id`, `stage_index`
  - `pipeline_id` (for fan-out)
  - `step_name`
  - typed input/output schema version
  - checksums and byte size
  - terminal status + error summary
  - artifact URIs for inputs, outputs, and logs
- If a step fails, the workflow can pause immediately after the failed step and enter `PAUSED` state.
- When a hot-fix is made, `replay_step` is allowed for:
  - a single scope: `stage_id + pipeline_id? + step_name`
  - optional `override_input_uri` (for manual input replacement)
  - optional `skip_artifact_verification` for emergency recovery

Run-side control payload example:

```yaml
step_replay:
  enabled: true
  replay_target:
    stage_id: joint_pretrain
    pipeline_id: joint_text_visual
    step_name: materialize_workload_bundle
    attempt: 1
  skip_artifact_verification: false
  override_input_uri: null
  allow_dry_run: false
```

### Data readiness simplification (`configure_training_data`)

The `configure_training_data` stage is intentionally one step and side-effect free:

- Verify the dataset URI/path is reachable.
- Verify required files/artifacts are present.
- Verify schema/format compatibility for the current stage contract.
- Verify minimum sample cardinality if configured.
- Verify stage-targeted data composition and token-budget compatibility.

No catalog writes, no registration calls, no cross-table state updates are performed in this step.

This stage must support high-complexity corpora with very large token budgets and modality splits (for example: pretraining tokens in the tens/hundreds of trillions, mixed visual/text sources, and explicit long-context curricula). It should be able to enforce constraints such as:

- minimum tokens per stage (e.g., ViT pretrain, joint pretrain, long-context stage),
- minimum mix composition (e.g., coding/text/math/science/visual proportions),
- minimum quality indicators per source shard,
- source-level dedupe and continuity checks when chaining stage inputs.

Example target profile to validate against:

- Stage 0 (`vit_pretrain`): `10_000_000_000_000` tokens, data mix target `{visual: 70.0, text: 30.0}`, minimum examples `50_000_000`.
- Stage 1 (`joint_pretrain`): `15_000_000_000_000` tokens, data mix target `{text: 45.0, code: 50.0, math: 3.0, science: 2.0}`, minimum examples `80_000_000`.
- Stage 2 (`long_context_midtrain`): `200_000_000_000` to `500_000_000_000` tokens per segment, data mix target `{code: 55.0, math: 20.0, science: 15.0, visual: 10.0}`, quality threshold `>= 0.98`.

### Stage execution control plane (`kilvin` training stages)

Each training stage is an explicit, typed unit of work with a standardized pre/post contract. Stage order is a run-level configuration field and can be a-la-carte:

- `stage_sequence`: ordered array
- `stage_id`: immutable identifier (`vit_pretrain`, `joint_pretrain`, `continue_pretrain`, `long_context_midtrain`, `cpt`, `sft`, `parl_rl`, `agentic_synthesis`, `qat`)
- `stage_type`: execution behavior selector (`pretrain`, `continued_pretrain`, `cpt`, `fine_tune`, `rl`, `post_train`)
- `phase`: `foundation` or `post_foundation` (used for policy defaults and cost controls)
- `enabled`: bool (allow dynamic inclusion/exclusion)
- `depends_on`: optional explicit dependency list for parallel-safe sequencing
- `pipeline_strategy`: optional stage-level policy for parallel pipeline execution
- `pipelines`: optional pipeline definitions (if omitted, defaults to a single implicit pipeline)

Reusable business-step sequence per stage:

1. `extract_stage_config`  
   - Resolve stage-specific config from the workflow-level config snapshot
   - Resolve component profile (`component_name`, precision mode, curriculum, tokenizer, optimizer preset)
   - Determine resource shape and hardware class hint
   - This step does not select or validate checkpoints
2. `validate_checkpoint`  
   - Select the input checkpoint for the stage
   - Validate checkpoint URI and manifest compatibility for the stage
   - Confirm resume behavior and optimizer/scheduler compatibility
3. `configure_training_data`  
   - Verify data source reachability and minimum schema
   - Verify stage token budget and modality composition constraints
   - Validate source continuity rules from previous stage if `previous_checkpoint` is chained
4. `allocate_resources`  
   - Reserve REAM resources for requested component topology
   - Emit machine-type bindings for each component + rank topology
   - Return per-pipeline allocation outputs
5. `materialize_workload_bundle` (parallelized per pipeline when `pipeline_strategy.mode=parallel`)  
   - Convert logical stage definition + validated checkpoint + allocation into a concrete workload bundle for each pipeline
   - Attach network/runtime envelope: RDMA/NCCL profile, fabric mapping, env vars, per-component launch commands, expected health checks
6. `submit_k8s_job` (parallelized per pipeline)  
   - Submit scheduler-native job + runtime metadata
   - Persist each bundle-to-job correlation id for observability
7. `monitor_training` (parallelized per pipeline)  
   - One long-running monitor per pipeline branch
   - Stage-level fan-in awaits all non-skippable monitor futures
   - Heartbeat polling includes pipeline identity in context
   - Emit deterministic terminal status back to workflow
8. `purge_resources` or stage transition  
   - On success, optionally release non-persistent resources and pass checkpoint forward
   - On failure, call `purge_resources` with `preserve_artifacts=true` when configured

Parallel pipeline execution details:

- `pipeline_strategy.mode = parallel` means per-stage pipelines execute through a fan-out stage.
- `pipeline_strategy.mode = serial` keeps the same stage pipeline order but runs each pipeline sequentially.
- `pipeline_strategy.max_parallelism` limits the number of concurrent active pipelines.
- `pipeline_strategy.join_behavior` defines how stage completion is computed from pipeline outcomes.

Fan-in policy:

- `all_required`: every pipeline must complete successfully.
- `all_or_skip_failed`: allow configured skippable pipelines to fail without stage failure.
- `fastest_success`: stage succeeds when any required pipeline succeeds; non-required/remaining pipelines are cancelled.

Stage outcome and checkpoint promotion rules:

- A stage completes only after pipeline fan-in evaluates terminal monitor outcomes.
- A stage terminal state must be one of: `SUCCEEDED`, `FAILED`, `CANCELLED`.
- Every successful stage produces exactly one promoted checkpoint for the next stage.
- The promoted checkpoint is the only checkpoint eligible to enter the next stage unless an explicit future override mode is added.
- `validate_checkpoint` for the next stage validates against the promoted checkpoint from the prior completed stage.
- `all_required`: every required pipeline must succeed; if any required pipeline fails, the stage fails, and the promoted checkpoint is derived from the full required successful set.
- `all_or_skip_failed`: skippable pipelines may fail without failing the stage, but at least one required pipeline must still succeed; the promoted checkpoint is derived only from successful required pipelines.
- `fastest_success`: the first successful required pipeline wins, remaining pipelines are cancelled as stragglers, and the winning pipeline output becomes the promoted checkpoint.
- Success from optional or probe pipelines alone is not sufficient to complete a stage.
- Pipeline terminal classification must distinguish `failed`, `skipped`, and `cancelled_by_join` so only blocking failures on required pipelines prevent stage advancement.

Parallel pipeline state tracking:

- `PipelineRunOutput` includes per-pipeline terminal status, failure reason, and checkpoint artifact path.
- On `fastest_success`, remaining active pipelines are explicitly cancelled so the workflow can proceed deterministically.
- On `all_or_skip_failed`, mark skipped/failed pipelines as non-blocking only if the pipeline is declared skippable in its config.

#### Step-level inspectability, pause, replay, and resume

For every stage/pipeline/step execution, the parent should support:

- `list_step_records`: returns all `StepExecutionEnvelope` entries for the run in execution order.
- `get_step_artifact`: returns artifact locations for one step (input, output, logs, environment manifest).
- `replay_step`: signal that re-executes exactly the requested step and then resumes the remainder of the workflow.

Replay semantics:

- `scope=stage` re-runs from the first failed step in a stage.
- `scope=pipeline` re-runs from the failed step in one pipeline branch only.
- `scope=step` re-runs the selected step only.
- `replay_step` can only target completed or failed steps; completed steps with unchanged `input_checksum` are skipped unless `force=true`.
- Downstream steps are reset in-memory in the workflow replay state and recomputed from the newly produced output artifacts.
- Existing artifact URIs remain immutable; new step reruns write to a new artifact path under the same run ID and a higher step attempt number.

Deterministic pause behavior:

- `pause_at_step` supports a pre-step and post-step hook, so maintainers can:
  - inspect `materialize_workload_bundle` output before job submit,
  - patch upstream data/config,
  - then `resume` to continue.
- Paused state also stores `resume_from_step` so a restart signal is deterministic in replay.

Canonical pipeline contract (copy into all stage configs):

```yaml
pipeline_id: string
pipeline_type: foundation_pretrain | long_context | parl_rl | agentic_synthesis | qat
component_name: string
component_version: string
modality_mix:
  text: 0.0
  visual: 0.0
  code: 0.0
  math: 0.0
  science: 0.0
  ocr: 0.0
  captions: 0.0
token_budget: string
sequence_length_target: 262144
quality_gate: 0.0
skippable: false
priority: required | optional | probe
transport_profile: rdma_v4_vswitch | topo_a2a | topo_intra_node
resource_selector:
  machine_family: string
  tensor_parallel: 1
  data_parallel: 1
  pipeline_parallel: 1
run_budget: 2x16H
spec:
  target_precision: fp16 | bf16 | int4 | int8
  max_steps: 0
  branch_role: string
  reward_components:
    - correctness
    - laziness_penalty
    - exhaustion_penalty
  trajectory_depth: short | medium | long | ultra_long
  data_profile: string
  eval_set: string
```

Interpretation rules:

- `pipeline_type` is the runtime dispatcher key.
- `spec` contains stage-specific fields; keys vary by `pipeline_type`.
- `skippable=true` only has effect under `all_or_skip_failed`.
- `run_budget` is optional and only meaningful for long-running RL or synthesis branches.

#### Foundation-stage parallel execution examples

The same stage can be represented with one or many pipelines. `vit_pretrain`, `joint_pretrain`, and `long_context_midtrain` are common foundation stages with different parallelization motives.

```yaml
stage_id: vit_pretrain
pipeline_strategy:
  mode: parallel
  max_parallelism: 2
  join_behavior: all_required
pipelines:
  - pipeline_id: vision_main
    pipeline_type: foundation_pretrain
    component_name: moonvit3d_encoder
    modality_mix:
      visual: 0.7
      text: 0.3
    token_budget: "500_000_000_000"
    quality_gate: 0.98
    transport_profile: rdma_v4_vswitch
    resource_selector:
      machine_family: h100_96g
      tensor_parallel: 8
  - pipeline_id: vision_aux
    pipeline_type: foundation_pretrain
    component_name: grounding_projection
    modality_mix:
      ocr: 0.5
      captions: 0.5
    token_budget: "500_000_000_000"
    quality_gate: 0.97
    transport_profile: rdma_v4_vswitch
    resource_selector:
      machine_family: h100_96g
      tensor_parallel: 4
```

Use `all_required` here because both visual branches produce checkpoint slices and launch-time assumptions that are required for model consistency.

```yaml
stage_id: joint_pretrain
pipeline_strategy:
  mode: parallel
  max_parallelism: 3
  join_behavior: all_required
pipelines:
  - pipeline_id: joint_text_text
    pipeline_type: foundation_pretrain
    component_name: foundation_pretrain_main_vit
    modality_mix:
      text: 0.45
      code: 0.50
      math: 0.03
    token_budget: 6T
    quality_gate: 0.98
    transport_profile: topo_a2a
    resource_selector:
      machine_family: h100_96g
      data_parallel: 8
  - pipeline_id: joint_text_visual
    pipeline_type: foundation_pretrain
    component_name: foundation_pretrain_text_visual_mix
    modality_mix:
      text: 0.45
      code: 0.40
      visual: 0.15
    token_budget: 5T
    quality_gate: 0.98
    transport_profile: topo_a2a
    resource_selector:
      machine_family: h100_96g
      data_parallel: 8
  - pipeline_id: joint_long_context_probe
    pipeline_type: foundation_pretrain
    component_name: foundation_pretrain_probe
    modality_mix:
      text: 0.50
      science: 0.15
      math: 0.15
      visual: 0.20
    token_budget: 4T
    quality_gate: 0.94
    transport_profile: topo_a2a
    skippable: true
    resource_selector:
      machine_family: h100_96g
      data_parallel: 4
    spec:
      branch_role: probe
```

`joint_pretrain` may fan out by modality/quality segments to reduce single-branch blast radius. This keeps continuity while still validating all major modality streams.

```yaml
stage_id: long_context_midtrain
pipeline_strategy:
  mode: parallel
  max_parallelism: 2
  join_behavior: all_or_skip_failed
pipelines:
  - pipeline_id: ctx_700b_primary
    pipeline_type: long_context
    component_name: navi_context_encoder
    sequence_length_target: 262144
    token_budget: 350B
    quality_gate: 0.98
    transport_profile: topo_a2a
    resource_selector:
      machine_family: h100_96g
      tensor_parallel: 16
    spec:
      data_focus: high_quality_code_science
  - pipeline_id: ctx_700b_residual
    pipeline_type: long_context
    component_name: navi_context_encoder
    sequence_length_target: 262144
    token_budget: 350B
    quality_gate: 0.94
    transport_profile: topo_a2a
    skippable: true
    resource_selector:
      machine_family: h100_80g
      tensor_parallel: 8
    spec:
      data_focus: mixed_visual_text
```

`all_or_skip_failed` allows the secondary branch to drop if its quality gate fails while keeping the primary branch authoritative for progression.

Usage guidance:

- Use `serial` for strict curriculum pacing where downstream quality checks rely on strict output ordering.
- Use `all_required` for stages where every branch contributes irreversible state needed for next-stage compatibility.
- Use `fastest_success` for exploratory ablations (e.g., two architecture candidates for the same stage slot) where only one successful branch is needed.

#### Post-foundation and control-plane examples

```yaml
stage_id: parl_rl
pipeline_strategy:
  mode: parallel
  max_parallelism: 2
  join_behavior: fastest_success
pipelines:
  - pipeline_id: orchestrator_actor_v1
    pipeline_type: parl_rl
    component_name: orchestrator_policy_v1
    quality_gate: 0.99
    run_budget: 2x16H
    resource_selector:
      machine_family: h100_96g
      tensor_parallel: 8
    transport_profile: topo_a2a
    spec:
      policy_template: ppo_orchestrator
      branch_role: policy_experiment
      reward_components:
        - correctness
        - laziness_penalty
        - exhaustion_penalty
      requires_reward_critic: true
  - pipeline_id: orchestrator_actor_v2
    pipeline_type: parl_rl
    component_name: orchestrator_policy_v2
    quality_gate: 0.99
    run_budget: 2x16H
    resource_selector:
      machine_family: h100_96g
      tensor_parallel: 8
    transport_profile: topo_a2a
    spec:
      policy_template: ppo_orchestrator_v2
      branch_role: policy_experiment
      reward_components:
        - correctness
        - laziness_penalty
        - exhaustion_penalty
      requires_reward_critic: true
  - pipeline_id: critic_probe
    pipeline_type: parl_rl
    component_name: value_critic_probe
    quality_gate: 0.92
    run_budget: 1x16H
    resource_selector:
      machine_family: h100_80g
      tensor_parallel: 4
    transport_profile: topo_a2a
    skippable: true
    spec:
      branch_role: critic_validation
      reward_components:
        - stability_check
        - value_loss_gate
      requires_reward_critic: true
```

`fastest_success` lets the stage continue after the first successful policy branch reaches a valid improvement threshold, which is useful for fast architecture exploration in PARL-style reward design.

```yaml
stage_id: agentic_synthesis
pipeline_strategy:
  mode: parallel
  max_parallelism: 4
  join_behavior: all_or_skip_failed
pipelines:
  - pipeline_id: tool_spec_gen_web_search
    pipeline_type: agentic_synthesis
    component_name: tool_spec_generator
    quality_gate: 0.85
    run_budget: 1x08H
    spec:
      pipeline_class: tool_spec_generation
      data_profile: real_api_tools
      trajectory_depth: long
      max_steps: 12
    resource_selector:
      machine_family: a100_40g
      data_parallel: 4
    transport_profile: topo_a2a
  - pipeline_id: agent_task_gen_code
    pipeline_type: agentic_synthesis
    component_name: agent_task_generator
    quality_gate: 0.90
    run_budget: 1x12H
    spec:
      pipeline_class: agent_task_generation
      data_profile: coding_workflows
      trajectory_depth: long
      max_steps: 10
    resource_selector:
      machine_family: a100_80g
      data_parallel: 4
    transport_profile: topo_a2a
  - pipeline_id: traj_rollout_eval
    pipeline_type: agentic_synthesis
    component_name: trajectory_generator
    quality_gate: 0.88
    run_budget: 2x24H
    spec:
      pipeline_class: trajectory_generation
      data_profile: multimodal_tools
      trajectory_depth: ultra_long
      max_steps: 24
    resource_selector:
      machine_family: h100_80g
      tensor_parallel: 4
    transport_profile: topo_a2a
    skippable: true
  - pipeline_id: trajectory_cleanup_probe
    pipeline_type: agentic_synthesis
    component_name: trajectory_cleanup
    quality_gate: 0.70
    run_budget: 1x06H
    spec:
      pipeline_class: trajectory_cleanup
      data_profile: low_signal_tooling
      trajectory_depth: short
      max_steps: 6
    resource_selector:
      machine_family: a100_40g
      data_parallel: 2
    skippable: true
    transport_profile: topo_a2a
```

`all_or_skip_failed` is preferred for synthetic pipelines because some generation branches are inherently noisy; failed branch outputs can be non-blocking while still requiring at least one strong synthesis trajectory stream.

```yaml
stage_id: qat
pipeline_strategy:
  mode: serial
  max_parallelism: 1
  join_behavior: all_required
pipelines:
  - pipeline_id: qat_int4_calibration
    pipeline_type: qat
    component_name: quant_calibrator
    quality_gate: 0.97
    spec:
      pipeline_class: quant_calibration
      target_precision: int4
      calibration_samples: 8192
      batch_sequence: 1024
    resource_selector:
      machine_family: h100_80g
      tensor_parallel: 4
    transport_profile: topo_intra_node
  - pipeline_id: qat_eval_smoke
    pipeline_type: qat
    component_name: post_quant_eval
    quality_gate: 0.99
    spec:
      pipeline_class: post_quant_eval
      target_precision: int4
      eval_set: foundational_smoke
    resource_selector:
      machine_family: h100_80g
      tensor_parallel: 2
    transport_profile: topo_intra_node
```

`qat` is intentionally serial and `all_required` to prevent a partially quantized checkpoint from being considered complete when calibration and validation are coupled.

#### Concrete stage catalog (foundation-first defaults, then post-foundation extension stages)

- `vit_pretrain` (stage_type=`pretrain`, phase=`foundation`)  
  - Inputs: image-text pairs + synthetic captions/groundings/OCR streams  
  - Typical target: `~1T` visual tokens  
  - Emphasis: visual encoder topology, image augment path, frame/pipeline settings  
  - Can run as multiple pipelines (for example: primary encoder and auxiliary frame/pattern pipeline) when configured.
- `joint_pretrain` (stage_type=`continued_pretrain`, phase=`foundation`)  
  - Inputs: mixed visual/text corpus (high code/science/math mix)  
  - Typical target: `~15T` tokens  
  - Emphasis: cross-modal alignment and long-form sequence stability  
  - Supports parallel pipelines to isolate modality streams while sharing the same checkpoint lineage.
- `continue_pretrain` (stage_type=`continued_pretrain`, phase=`foundation`)  
  - Inputs: checkpoint continuation from K2 and/or previous stage output  
  - Typical target: additional high-volume mixed corpus run (example: K2->K2.5 continuation)  
  - Emphasis: curriculum continuity and shard consistency checks
- `long_context_midtrain` (stage_type=`pretrain`, phase=`foundation`)  
  - Inputs: curated high-quality long-context corpora  
  - Typical target: `500B`–`700B` tokens at 256k curriculum points  
  - Emphasis: context-length rollout constraints, sequence packing behavior
- `cpt` (stage_type=`pretrain`, phase=`post_foundation`)  
  - Inputs: continued pretraining component subset, usually language-only heavy mix  
  - Emphasis: stable transfer from previous multimodal checkpoints to compacted task-specific curriculum
- `sft` (stage_type=`fine_tune`, phase=`post_foundation`)  
  - Inputs: supervised fine-tune data, optional style/task instruction corpora  
  - Emphasis: instruction-following behavior under current architecture
- `parl_rl` (stage_type=`rl`, phase=`post_foundation`)  
  - Inputs: reward model signals, rollout traces, and branch-level latency signals  
  - Emphasis: orchestrator-centric optimization with penalties for laziness and exhaustion
  - Reward objective includes correctness + latency-weighted branch efficiency (critical-path minimization)
  - Can run parallel policy/rollout pipelines under a single stage run when experimentation requires separate reward branches.
- `agentic_synthesis` (stage_type=`post_train`, phase=`post_foundation`)  
  - Inputs: tool and trajectory datasets for tool-use simulation  
  - Emphasis: staged data synthesis, long sequence generation, branch pruning rules
- `qat` (stage_type=`post_train`, phase=`post_foundation`)  
  - Inputs: full trained model + calibration assets  
  - Emphasis: quantization-aware fine-tuning readiness and INT4 deployment profile

Failure behavior and resume:

- Each stage stores an immutable `stage_result` in workflow local state (typed output only).
- If a stage fails, workflow marks it `FAILED` and fails run unless `retry` policy allows resume at next retry attempt.
- On `run_id` replay, Temporal resumes at the last completed stage, reusing persisted outputs in history without re-running prior stage logic.

## Python Version (`kilvin-py`)

### Python SDK idioms used
- Async-first workflow code (`async def`), dataclass/Pydantic typed payloads.
- `workflow` API (`workflow.execute_activity`, `workflow.execute_child_workflow`).
- Activity side effects kept out of workflow thread.
- `@dataclass` / `BaseModel` payloads and explicit serializer checks.
- Separate `Activities` class with stateless activity methods.

### Layout suggestion

```text
kilvin_python/
  client.py         # start/reconnect/run command APIs
  workflows/
    parent.py
    training.py
  activities/
    training_activities.py
  models/
    models.py       # typed inputs/outputs and state models
  signals.py        # pause/resume/cancel message shapes
  worker.py         # worker bootstrapping and registration
```

### Workflow pattern (Python)

- `ParentKilvinCmdWorkflow`:
  1. `extract_workflow_config` activity
  2. start child workflow `KilvinTrainingWorkflow` with `ChildWorkflowOptions` (run timeout + retry)
  3. update final run state via `update_cmd_state`
- `KilvinTrainingWorkflow`:
 1. `dev_prepare`
  2. loop over `workflow_config.stages` (ordered by `stage_sequence`):
     - call `extract_stage_config`, `validate_checkpoint`, `configure_training_data`
     - call `allocate_resources` once, obtaining per-pipeline allocations
     - build pipeline list:
       - `pipelines = stage.pipelines if non-empty else [implicit_default_pipeline]`
       - each branch includes `pipeline_id` and component/network/rank intent
     - execute per-pipeline branches:
       - `mode = serial`: await each branch end-to-end
       - `mode = parallel`: submit branch workflows/activities as futures respecting `max_parallelism`
     - each branch does:
       - `materialize_workload_bundle` (per pipeline)
       - `submit_k8s_job` (per pipeline)
       - `monitor_training` as a long-running future
     - wait for fan-in according to `pipeline_strategy.join_behavior`
       - `all_required`: every branch must reach terminal success
       - `all_or_skip_failed`: skip explicitly skippable branch failures
       - `fastest_success`: accept first success and cancel stragglers
     - optionally call `purge_resources` on failed optional pipelines
  3. `purge_resources` for stage-level release if stage completed and configured

  Example pseudo-code:

  ```python
  async def run_pipeline_stage(ctx, stage, strategy, workflow_config):
      pipelines = stage.pipelines or [default_pipeline(stage)]
      mode = strategy.mode if strategy else "parallel"
      max_parallel = max(1, strategy.max_parallelism if strategy else len(pipelines))

      active = []
      for pipeline in pipelines:
          branch = execute_pipeline(ctx, stage, pipeline)
          active.append(branch)
          if mode == "parallel" and len(active) >= max_parallel:
              done, active = await wait_for_any(active)
              status = await handle_done(done, strategy.join_behavior)
              if status.terminal and strategy.join_behavior == "fastest_success":
                  await cancel_any(active)
                  return status

      while active:
          done, active = await wait_for_any(active)
          await handle_done(done, strategy.join_behavior)
  ```

  Default stage sequence for foundation-first runs:
  - `vit_pretrain` -> `joint_pretrain` -> `continue_pretrain` -> `long_context_midtrain`

### Python typed contracts

Use immutable-ish dataclasses for cross-step contracts:

- `ExtractCmdConfigOutput`, `CheckpointOutput`, `DataConfigureOutput`, `ReamAllocationOutput`, `MaterializedBundleOutput`, `SubmitOutput`, `MonitorOutput`
- `StepIOArtifact`, `StepExecutionEnvelope`
- `PipelineAllocation`, `PipelineMaterializedBundleInput`, `PipelineBundleOutput` (all optional aliases when pipeline fan-out is active)

All steps return their specific output type and next steps consume only typed input.

```python
@dataclass(frozen=True)
class StepIOArtifact:
    uri: str
    format: Literal["yaml"]
    checksum_sha256: str
    size_bytes: int


@dataclass(frozen=True)
class StepExecutionEnvelope:
    run_id: str
    run_attempt: int
    stage_id: str
    stage_index: int
    step_name: str
    pipeline_id: str | None = None
    pipeline_index: int | None = None
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED", "PAUSED"]
    retry_attempt: int
    input_artifact: StepIOArtifact
    output_artifact: StepIOArtifact | None
    error: str | None = None
    input_checksum: str
    output_checksum: str | None = None
    command: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

#### Simplified data readiness contract (`configure_training_data`)

The stage is intentionally simplified to a single deterministic configuration activity: confirm required files exist, schema/format matches, and minimum cardinality is met. Any failed check must fail the activity (non-retryable by default). No external registration is performed here; that belongs to bundle materialization.

```python
@dataclass(frozen=True)
class DataConfigureInput:
    dataset_uri: str
    dataset_stage: str
    config_snapshot: str
    required_files: list[str]
    required_token_budget: int
    min_examples: int | None = None
    token_budget_tolerance_ratio: float = 0.0
    data_mix_requirements: dict[str, float] | None = None
    quality_thresholds: dict[str, float] | None = None


@dataclass(frozen=True)
class DataConfigureOutput:
    dataset_id: str
    schema_version: str
    shard_count: int
    estimated_tokens: int | None = None
    stage_token_mix: dict[str, int]
    composition_breakdown: dict[str, float]
    quality_scores: dict[str, float] | None = None
    total_examples: int | None = None
    format_ok: bool = True
    validation_report_path: str | None = None


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
```

#### Materialization contract (`materialize_workload_bundle`)

The materialization step now sits after resource allocation and is the point where logical training components become concrete runtime topology.

```python
@dataclass(frozen=True)
class AllocationBinding:
    component_name: str
    machine_type: str
    pool_name: str
    node_count: int
    gpu_count_per_node: int
    rank_size: int


@dataclass(frozen=True)
class RuntimeNetworkSetup:
    rdma_enabled: bool
    nccl_transport: str          # e.g., nccl
    nccl_net: str                # e.g., ib
    fabric_profile: str
    network_placement: list[str] # hostnames/ranges/labels


@dataclass(frozen=True)
class MaterializedBundleInput:
    # Upstream outputs
    ir_name: str
    checkpoint: str
    config_snapshot: str
    pipeline_id: str
    # Data readiness context
    data_config: DataConfigureOutput
    # Allocation-derived constraints
    allocation: PipelineAllocation
    stage_index: int
    train_stage: str             # pretrain | cpt | sft | rl
    task_type: str               # training | mixed_precision | eval
    pipeline_profile: PipelineConfig
    # Training runtime knobs
    total_tokens_target: int
    global_batch_tokens: int
    max_steps: int
    learning_rate: float
    model: str


@dataclass(frozen=True)
class MaterializedBundleOutput:
    bundle_id: str
    bundle_path: str             # manifest path in object store
    bound_components: list[AllocationBinding]
    runtime_setup: RuntimeNetworkSetup
    rendezvous: dict[str, str]   # rank/rank_set/world_size + discovery endpoints
    launch_plan: list[dict]      # container args + env + command
    token_plan: dict[str, int]   # token budget and allocation per component
    health_checks: list[str]     # expected checks before submit
    estimated_wall_clock_ratio: float | None = None


@dataclass(frozen=True)
class PipelineBundleOutput:
    pipeline_id: str
    bundle: MaterializedBundleOutput
```

#### Materialization contract mapping in Go

```go
type DataConfigureInput struct {
    DatasetURI       string   `json:"dataset_uri"`
    DatasetStage     string   `json:"dataset_stage"`
    ConfigSnapshot   string   `json:"config_snapshot"`
    RequiredFiles    []string `json:"required_files"`
    MinExamples      int      `json:"min_examples"`
    RequiredTokenBudget int   `json:"required_token_budget"`
    TokenBudgetToleranceRatio float64 `json:"token_budget_tolerance_ratio"`
    DataMixRequirements map[string]float64 `json:"data_mix_requirements"`
    QualityThresholds map[string]float64 `json:"quality_thresholds"`
}

type DataConfigureOutput struct {
    DatasetID           string         `json:"dataset_id"`
    SchemaVersion       string         `json:"schema_version"`
    ShardCount          int            `json:"shard_count"`
    EstimatedTokens      int           `json:"estimated_tokens"`
    StageTokenMix       map[string]int `json:"stage_token_mix"`
    CompositionBreakdown map[string]float64 `json:"composition_breakdown"`
    QualityScores       map[string]float64 `json:"quality_scores"`
    TotalExamples       int            `json:"total_examples"`
    FormatOK            bool           `json:"format_ok"`
    ValidationReportPath string         `json:"validation_report_path"`
}

type PipelineAllocation struct {
    PipelineID      string `json:"pipeline_id"`
    ComponentName   string `json:"component_name"`
    NodeCount       int    `json:"node_count"`
    GPUsPerNode     int    `json:"gpus_per_node"`
    RankSize        int    `json:"rank_size"`
    MachineType     string `json:"machine_type"`
    PoolName        string `json:"pool_name"`
    RDMAEnabled     bool   `json:"rdma_enabled"`
    NCCLProfile     string `json:"nccl_profile"`
    Rendezvous      map[string]string `json:"rendezvous"`
}

type ReamAllocationOutput struct {
    AllocationID       string              `json:"allocation_id"`
    ResourceEpoch      int                 `json:"resource_epoch"`
    PoolsReservationID string              `json:"pools_reservation_id"`
    PipelineAllocations []PipelineAllocation `json:"pipeline_allocations"`
}

type AllocationBinding struct {
    ComponentName     string `json:"component_name"`
    MachineType       string `json:"machine_type"`
    PoolName          string `json:"pool_name"`
    NodeCount         int    `json:"node_count"`
    GPUCountPerNode   int    `json:"gpu_count_per_node"`
    RankSize          int    `json:"rank_size"`
}

type RuntimeNetworkSetup struct {
    RDMAEnabled    bool     `json:"rdma_enabled"`
    NCCLTransport  string   `json:"nccl_transport"`
    NCCLNet        string   `json:"nccl_net"`
    FabricProfile  string   `json:"fabric_profile"`
    NetworkTargets []string `json:"network_placement"`
}

type MaterializedBundleInput struct {
    IRName          string              `json:"ir_name"`
    Checkpoint      string              `json:"checkpoint"`
    ConfigSnapshot  string              `json:"config_snapshot"`
    PipelineID      string              `json:"pipeline_id"`
    Allocation      PipelineAllocation  `json:"allocation"`
    PipelineProfile PipelineConfig      `json:"pipeline_profile"`
    StageIndex     int                 `json:"stage_index"`
    TrainStage     string              `json:"train_stage"`
    TaskType       string              `json:"task_type"`
    TotalTokensTarget int              `json:"total_tokens_target"`
    GlobalBatchTokens int              `json:"global_batch_tokens"`
    MaxSteps       int                 `json:"max_steps"`
    LearningRate   float64             `json:"learning_rate"`
    Model          string              `json:"model"`
}

type MaterializedBundleOutput struct {
    BundleID      string                 `json:"bundle_id"`
    BundlePath    string                 `json:"bundle_path"`
    BoundComponents []AllocationBinding `json:"bound_components"`
    RuntimeSetup  RuntimeNetworkSetup    `json:"runtime_setup"`
    Rendezvous    map[string]string      `json:"rendezvous"`
    LaunchPlan    []map[string]any       `json:"launch_plan"`
    TokenPlan     map[string]int         `json:"token_plan"`
    HealthChecks  []string               `json:"health_checks"`
    PipelineID    string                 `json:"pipeline_id"`
}

type PipelineBundleOutput struct {
    PipelineID string                `json:"pipeline_id"`
    Bundle     MaterializedBundleOutput `json:"bundle"`
}
```

### Python observability and failure semantics

- Every activity call includes `activity_id`, `run_id`, `kilvin_job_id` in headers/log context.
- Every step writes `StepExecutionEnvelope` records via `artifact_store.log_step_envelope`.
- Inputs and outputs are stored as immutable artifacts before/after step execution to support replay.
- Failed step behavior:
  - write `FAILED` envelope with `error`, `output_artifact` (if partial), and resume cursor
  - optionally auto-pause if `run_policy.pause_on_step_failure` is enabled
  - no downstream stages can advance until operator signals `resume` or `replay_step`
- Parent catches child failure and sets run state to failed.

Reusable step wrapper pattern:

```python
async def run_step(ctx, step_name, stage, pipeline, step_input, step_func):
    attempt = await next_attempt(step_name, stage, pipeline)
    input_artifact = await persist_step_artifact(step_name, stage, pipeline, step_input, attempt)
    env = StepExecutionEnvelope(
      run_id=ctx.info.run_id,
      run_attempt=ctx.info.attempt,
      stage_id=stage.stage_id,
      stage_index=stage.stage_index,
      step_name=step_name,
      pipeline_id=pipeline.pipeline_id if pipeline else None,
      status="RUNNING",
      retry_attempt=attempt,
      input_artifact=input_artifact,
      input_checksum=input_checksum(step_input),
    )
    await write_envelope(env)
    try:
        output = await step_func(ctx, step_input)
        output_artifact = await persist_step_artifact(step_name, stage, pipeline, output, attempt, suffix="out")
        env.output_artifact = output_artifact
        env.output_checksum = output_checksum(output)
        env.status = "SUCCEEDED"
        env.completed_at = utcnow()
        await write_envelope(env)
        return output
    except Exception as exc:
        env.status = "FAILED"
        env.error = str(exc)
        env.completed_at = utcnow()
        await write_envelope(env)
        raise
```

### Python monitor activity

- `async def monitor_training(ctx, input)`
- On each poll, read heartbeat details to resume safely:
  - If `activity.has_heartbeat_details(ctx)` exists, deserialize and continue.
- Write periodic heartbeat containing:
  - last poll timestamp
  - observed k8s/Primus state
- Return `MonitorOutput` with final status or raise terminal error.

### Python query/signal behavior

- Query `run_status`, `run_step_trace`, `run_artifacts`, `run_plan`
- Signal:
  - `pause`
  - `resume`
  - `cancel`
  - `pause_at_step`
  - `replay_step`
- `pause_at_step` payload: `{stage_id, pipeline_id, step_name, when: pre|post}`
- `replay_step` payload:
  - `scope`: `step|pipeline|stage`
  - `target_stage_id`
  - `target_pipeline_id` (optional)
  - `target_step`
  - `force`: false by default
  - `override_input_uri` (optional)
  - `reason` (required)
- Parent/child propagate cancellation via `workflow.cancelled()` and `workflow.info().is_running` guards.

### Notable Python-specific advantages

- Concise business-flow code in async style close to existing training script style.
- Native `pydantic` validation near model boundaries.
- Rich local unit testing of pure functions plus deterministic workflow simulation via Replay/Replayer.

## Go Version (`kilvin-go`)

### Go SDK idioms used
- Explicit `workflow.Context` signatures.
- Deterministic workflow code with local helpers.
- `workflow.ExecuteActivity`, `workflow.ExecuteChildWorkflow` and retry policy structs.
- Separate registration of workflows/activities in `worker.Worker`.
- Typed structs + compile-time checks.

### Layout suggestion

```text
kilvin_go/
  cmd/
    kilvin-worker/main.go
    kilvin-client/main.go
  workflows/
    parent.go
    training.go
    helpers.go
  activities/
    training_activities.go
  model/
    types.go
  client/
    client.go
```

### Workflow pattern (Go)

- `ParentKilvinCmdWorkflow(ctx, in)`:
  - configure activity options with retries/timeouts
  - execute `ExtractCmdConfig` activity and inspect output
  - create child options and execute `KilvinTrainingWorkflow`
  - execute `UpdateCmdState`

- `KilvinTrainingWorkflow(ctx, in)`:
  - typed local variables through each stage
  - optional multi-stage loop with per-stage pipeline fan-out:

```go
for i, stage := range in.WorkflowConfig.Stages {
    stageInput := NewStageInput(in, stage, i)
    if err := executeStageHead(ctx, stageInput, &stageOut); err != nil { return ..., err }

    pipelines := stage.Pipelines
    if len(pipelines) == 0 {
        pipelines = []PipelineConfig{DefaultPipelineFromStage(stage)}
    }

    allocInput := AllocateInput{StageID: stage.StageID, StageIndex: i}
    var alloc ReamAllocationOutput
    if err := workflow.ExecuteActivity(ctx, "AllocateResources", allocInput).Get(ctx, &alloc); err != nil {
        return TrainingWorkflowOutput{}, err
    }

    strategy := stage.PipelineStrategy
    if strategy.MaxParallelism <= 0 {
        strategy.MaxParallelism = len(pipelines)
    }
    maxParallel := strategy.MaxParallelism
    serialMode := strategy.Mode == "serial" || len(pipelines) == 1

    futures := make([]workflow.Future, 0, maxParallel)
    active := 0
    for _, pipeline := range pipelines {
        p := pipeline
        if !serialMode && active >= maxParallel {
            for _, future := range futures {
                var result PipelineRunOutput
                if err := future.Get(ctx, &result); err != nil {
                    return TrainingWorkflowOutput{}, err
                }
                if err := handlePipelineResult(ctx, stage.PipelineStrategy, result); err != nil {
                    return TrainingWorkflowOutput{}, err
                }
                active--
            }
            futures = futures[:0]
        }

        fut := workflow.ExecuteActivity(ctx, "RunPipeline", PipelineRunInput{
            StageID:    stage.StageID,
            Pipeline:   p,
            StageIndex: i,
            DataConfig: stageOut.DataConfig,
            Allocation: selectPipelineAllocation(alloc, p.PipelineID),
        })
        futures = append(futures, fut)
        active++
        if serialMode {
            var result PipelineRunOutput
            if err := fut.Get(ctx, &result); err != nil {
                return TrainingWorkflowOutput{}, err
            }
            if err := handlePipelineResult(ctx, stage.PipelineStrategy, result); err != nil {
                return TrainingWorkflowOutput{}, err
            }
            active--
            futures = futures[:0]
        }
    }

    for _, fut := range futures {
        var result PipelineRunOutput
        if err := fut.Get(ctx, &result); err != nil {
            return TrainingWorkflowOutput{}, err
        }
        if err := handlePipelineResult(ctx, stage.PipelineStrategy, result); err != nil {
            return TrainingWorkflowOutput{}, err
        }
    }

    in.PreviousCheckpoint = stageOut.CheckpointPath
}
```

Default foundation-first sequence (if enabled in run config):
- `vit_pretrain` -> `joint_pretrain` -> `continue_pretrain` -> `long_context_midtrain`

### Go typed contracts

- `type ExtractCmdConfigOutput struct {...}`
- `type CheckpointOutput struct {...}`
- `type DataConfigureOutput struct {...}`
- `type StepIOArtifact struct {...}`
- `type StepExecutionEnvelope struct {...}`
- `type ReamAllocationOutput struct {...}`
- `type K8sSubmitOutput struct {...}`
- `type MonitorOutput struct { FinalStatus string ... }`

```go
type StepIOArtifact struct {
	URI          string `json:"uri"`
	Format       string `json:"format"`
	ChecksumSHA  string `json:"checksum_sha"`
	SizeBytes    int64  `json:"size_bytes"`
}

type StepExecutionEnvelope struct {
	RunID            string               `json:"run_id"`
	RunAttempt       int                  `json:"run_attempt"`
	StageID          string               `json:"stage_id"`
	StageIndex       int                  `json:"stage_index"`
	PipelineID       *string              `json:"pipeline_id"`
	PipelineIndex    *int                 `json:"pipeline_index"`
	StepName         string               `json:"step_name"`
	Status           string               `json:"status"`
	RetryAttempt     int                  `json:"retry_attempt"`
	InputArtifact    StepIOArtifact       `json:"input_artifact"`
	OutputArtifact   *StepIOArtifact      `json:"output_artifact"`
	Error            *string              `json:"error"`
	InputChecksum    string               `json:"input_checksum"`
	OutputChecksum   *string              `json:"output_checksum"`
	Command          string               `json:"command"`
	StartedAtMs      int64                `json:"started_at_ms"`
	CompletedAtMs    *int64               `json:"completed_at_ms"`
}
```

### Go monitor activity

- `func (a *TrainingActivities) MonitorTraining(ctx context.Context, input MonitorTrainingInput) (MonitorOutput, error)`
- Resume from `activity.GetHeartbeatDetails(ctx, &state)` if present.
- Poll k8s/Primus with backoff sleep loop in activity context.
- Return terminal statuses `SUCCEEDED`, `FAILED`, `KILLED`, etc.
- Use `activity.RecordHeartbeat(ctx, MonitorHeartbeat{...})` each poll.

### Go error and cancellation wiring

- Parent workflow catches child workflow error and sets `cmdState="KILVIN_CMD_FAILED"`.
- Explicit child `WorkflowID` pattern (e.g., `kilvin-training-{run_id}-{attempt}`) for deterministic retries/resume.
- `workflow.WithActivityOptions` and `workflow.WithChildOptions` keep cancellation and replay deterministic.

### Go query/signal behavior

- Register query handlers:
  - `run_status`
  - `run_step_trace`
  - `run_artifacts`
  - `run_plan`
- Register signal handlers:
  - `pause`
  - `resume`
  - `cancel`
  - `pause_at_step`
  - `replay_step`
- For replay handlers, parse replay payload into deterministic target state:
  - verify target stage/pipeline/step exists in resolved run plan
  - validate artifact checksums when `force=false`
  - rewrite local workflow cursor only at deterministic boundaries (never mutate arbitrary history)

### Notable Go-specific advantages

- Strong compile-time guarantees across large command payloads.
- Lower per-call overhead in hot loops; straightforward long-term maintainability for ops tooling.
- Clear operational code split between workflow definitions and activity implementations.

## Language Adaptation Matrix

| Concern | Python (`kilvin-py`) | Go (`kilvin-go`) |
|---|---|---|
| Concurrency model | `asyncio` driven, awaitable workflow/activities | Explicit goroutine-free workflow function boundaries |
| Serialization | pydantic/dataclasses + runtime validation | Structs + `encoding/json` / proto converter compatibility |
| Replay testing | Activity mocking + Replayer utilities | Unit tests with `workflowtest`/SDK test env | 
| Long-run heartbeat | `activity.record_heartbeat` details in activity context | `activity.RecordHeartbeat` + typed heartbeat struct |
| Local runtime | Async workers + bootstrap helper | Simple worker CLI with env profile |
| API ergonomics | `start_kilvin_command(...)` convenience wrappers | `client.StartKilvinCommand(...)` with options | 

## Milestones

### M1: Foundation (both versions, same week)
- Define shared payload contract schema docs (`kilvin` naming).
- Implement `ParentKilvinCmdWorkflow` + `KilvinTrainingWorkflow` in both languages.
- Build `submit + monitor + finalize` happy path only.

### M2: Robustness (next)
- Add full activity retry policies and error mapping.
- Add monitor heartbeat/retry correctness tests.
- Add pause/resume/cancel signals + status queries.

### M3: Multi-stage and parity
- Add staged loop over stage configs in training workflow.
- Add observability logging + result envelopes.
- Add optional dry-run and validation-only mode.

## Non-goals (v0)

- No reuse of legacy scheduler tables.
- No compatibility parser for legacy blob contexts.
- No migration of old active jobs in this first cut.

## Success Criteria

- Re-run path is a single deterministic Temporal history per `kilvin` command.
- No hand-rolled poll loops for orchestration state.
- One typed contract per activity boundary.
- Monitor recovery works after worker restart (heartbeats continue from last poll).
- Same business behavior can be implemented in both `kilvin-py` and `kilvin-go` under a shared design contract.
