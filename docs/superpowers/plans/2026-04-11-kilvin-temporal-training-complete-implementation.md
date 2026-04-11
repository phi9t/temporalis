# Kilvin Temporal Training Complete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the remaining core execution, replay, validation, and query-contract scope from `docs/superpowers/specs/2026-04-11-kilvin-temporal-training-design.md` in both `kilvin-py` and `kilvin-go`, with parity on join behavior and stage/pipeline semantics.

**Architecture:** Introduce a shared execution contract in each runtime by adding explicit preflight validation, strict plan normalization, and stage-level runtime policy enforcement, then update pipeline fan-out/fan-in orchestration to honor `join_behavior` and replay scope/ checksum rules.

**Tech Stack:** Python 3.11 + Temporal Python SDK, Go + Temporal Go SDK, YAML/YAML-canonicalization, no external test dependencies beyond pytest and `go test`.

---

### Task 1: Canonicalize run/pipeline model fields in spec and both runtimes

**Files:**
- Modify: `docs/superpowers/specs/2026-04-11-kilvin-temporal-training-design.md`
- Modify: `kilvin-py/kilvin_py/models.py`
- Modify: `kilvin-go/models.go`
- Modify: `kilvin-py/worker.py`
- Modify: `kilvin-go/activities.go`

- [ ] **Step 1: Update contract text for join-behavior compatibility and aliases**

Edit `docs/superpowers/specs/2026-04-11-kilvin-temporal-training-design.md` by adding one short section after the existing `RunConfig validation rules` block:

```markdown
### Compatibility and alias policy
- `pipeline_strategy.join_behavior` canonical values are `all_required`, `all_or_skip_failed`, `fastest_success`.
- Inputs may use legacy `allow_partial`; runtimes MUST normalize it to `all_or_skip_failed` during model binding.
- `skippable`, `priority`, and `priority`-dependent scheduling are required fields on `PipelineConfig`.
```

- [ ] **Step 2: Add canonical enums and normalize legacy inputs in Python models**

Modify `kilvin-py/kilvin_py/models.py` with new canonical enums and migration helpers:

```python
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
class PipelineStrategy:
    mode: Literal["serial", "parallel"] = "parallel"
    max_parallelism: int | None = None
    join_behavior: JoinBehavior | str = JoinBehavior.ALL_REQUIRED

    def normalized_join_behavior(self) -> str:
        if self.join_behavior == JoinBehavior.ALLOW_PARTIAL or str(self.join_behavior) == "allow_partial":
            return JoinBehavior.ALL_OR_SKIP_FAILED.value
        return str(self.join_behavior)


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
```

- [ ] **Step 3: Update Go data models for canonical fields and compatibility handling**

Modify `kilvin-go/models.go` near `PipelineStrategy` and `PipelineConfig`.

```go
// PipelineJoinBehavior constants live near PipelineStrategy.
type PipelineJoinBehavior string

const (
	JoinBehaviorAllRequired     PipelineJoinBehavior = "all_required"
	JoinBehaviorAllOrSkipFailed PipelineJoinBehavior = "all_or_skip_failed"
	JoinBehaviorFastestSuccess  PipelineJoinBehavior = "fastest_success"
	joinBehaviorAllowPartial    PipelineJoinBehavior = "allow_partial"
)

func NormalizeJoinBehavior(v string) PipelineJoinBehavior {
	switch v {
	case "allow_partial":
		return JoinBehaviorAllOrSkipFailed
	case "all_required", "all_or_skip_failed", "fastest_success":
		return PipelineJoinBehavior(v)
	default:
		return JoinBehaviorAllRequired
	}
}

type PipelinePriority string

const (
	PipelinePriorityRequired PipelinePriority = "required"
	PipelinePriorityOptional PipelinePriority = "optional"
	PipelinePriorityProbe    PipelinePriority = "probe"
)

type PipelineStrategy struct {
	Mode           string            `yaml:"mode"`
	MaxParallelism *int              `yaml:"max_parallelism,omitempty"`
	JoinBehavior   string            `yaml:"join_behavior"`
}

type PipelineConfig struct {
	PipelineID       string             `yaml:"pipeline_id"`
	ComponentName    string             `yaml:"component_name"`
	ComponentVersion string             `yaml:"component_version"`
	MachineType      string             `yaml:"machine_type,omitempty"`
	NodeCount        int                `yaml:"node_count"`
	GPUsPerNode      int                `yaml:"gpus_per_node"`
	RankSize         int                `yaml:"rank_size"`
	ResourcePool     string             `yaml:"resource_pool,omitempty"`
	RDMAProfile      *string            `yaml:"rdma_profile,omitempty"`
	NCCLProfile      *string            `yaml:"nccl_profile,omitempty"`
	MaxSeqLen        *int               `yaml:"max_seq_len,omitempty"`
	ModalityMix      map[string]float64 `yaml:"modality_mix,omitempty"`
	TransportProfile *string            `yaml:"transport_profile,omitempty"`
	PipelineType     string             `yaml:"pipeline_type"`
	Skippable        bool               `yaml:"skippable,omitempty"`
	Priority         PipelinePriority   `yaml:"priority"`
	StageOverrides   map[string]any     `yaml:"stage_overrides,omitempty"`
}
```

- [ ] **Step 4: Normalize alias behavior in both command entrypoints**

In Python, update any parser/builder path before workflow execution so legacy `allow_partial` is converted into `all_or_skip_failed` with no external behavior change. In Go, ensure `Run` or dedicated load step applies `NormalizeJoinBehavior` to every stage strategy.

Expected: both runtimes accept `allow_partial` and produce equivalent internal semantics to `all_or_skip_failed`.

---

### Task 2: Add preflight stage graph validation and deterministic ordering

**Files:**
- Modify: `kilvin-py/kilvin_py/workflows.py`
- Modify: `kilvin-go/workflows.go`
- Create: `kilvin-py/tests/test_stage_validation.py`
- Create: `kilvin-go/validation.go`
- Create: `kilvin-go/validation_test.go`

- [ ] **Step 1: Implement Python ordered stage validator and failure envelope**

Add at top of `kilvin-py/kilvin_py/workflows.py`:

```python
ALLOWED_STAGE_IDS = {
    "vit_pretrain",
    "joint_pretrain",
    "continue_pretrain",
    "long_context_midtrain",
    "cpt",
    "sft",
    "parl_rl",
    "agentic_synthesis",
    "qat",
}

FOUNDATION_SEQUENCE = ["vit_pretrain", "joint_pretrain", "continue_pretrain", "long_context_midtrain"]


def _validate_run_config(config: RunConfig) -> None:
    if not config.stage_sequence:
        raise ValueError("stage_sequence must not be empty")
    stage_by_id = {stage.stage_id: stage for stage in config.stages}
    unknown = [sid for sid in config.stage_sequence if sid not in stage_by_id]
    if unknown:
        raise ValueError(f"unknown stage_id in stage_sequence: {unknown}")

    stages = _ordered_stages(config)
    if not stages:
        raise ValueError("No enabled stages configured")

    seen = set()
    for idx, sid in enumerate(config.stage_sequence):
        if sid in seen:
            raise ValueError(f"duplicate stage_id in stage_sequence: {sid}")
        seen.add(sid)

    foundation_ids = [sid for sid in config.stage_sequence if sid in FOUNDATION_SEQUENCE]
    if foundation_ids != [sid for sid in FOUNDATION_SEQUENCE if sid in foundation_ids]:
        raise ValueError("foundation stages must preserve vit/joint/continue/long_context order")

    for stage in stages:
        if stage.phase == "foundation" and stage.stage_id not in FOUNDATION_SEQUENCE:
            raise ValueError(f"invalid foundation stage_id {stage.stage_id}")

    for stage in stages:
        for dep in stage.depends_on or []:
            if dep not in stage_by_id:
                raise ValueError(f"depends_on unknown stage {dep}")
```

Then call `_validate_run_config(input.run_config)` at the start of `TrainingWorkflow.run` before step execution.

- [ ] **Step 2: Add failing Python validation test**

Create `kilvin-py/tests/test_stage_validation.py`:

```python
import pytest

from kilvin_py.models import RunConfig, RunPolicy, StageConfig, StageDatasetProfile, StageRuntimeProfile, RunConfig
from kilvin_py.workflows import _validate_run_config


def test_rejects_duplicate_stage_sequence() -> None:
    cfg = RunConfig(
        run_id="r1",
        kilvin_run_name="bad",
        workflow_spec="x",
        policy=RunPolicy(),
        stage_sequence=["vit_pretrain", "vit_pretrain"],
        stages=[
            StageConfig(
                stage_id="vit_pretrain",
                stage_type="pretrain",
                phase="foundation",
                enabled=True,
                dataset_profile=StageDatasetProfile(uri="u", min_examples=1, token_budget=1),
                runtime_profile=StageRuntimeProfile(total_tokens_target=1, max_steps=1, global_batch_tokens=1, learning_rate=1.0),
            )
        ],
    )

    with pytest.raises(ValueError, match="duplicate stage_id"):
        _validate_run_config(cfg)
```

- [ ] **Step 3: Implement equivalent Go validation module**

Create `kilvin-go/validation.go` with dedicated validation functions (for example, `ValidateRunConfig` returning `error`) and a canonical allowed stage list.

- [ ] **Step 4: Add failing Go validation test**

Create `kilvin-go/validation_test.go` that checks unknown `stage_sequence` entries and duplicate detection.

- [ ] **Step 5: Wire validation before execution in both training run paths**

In both `TrainingWorkflow.Run` methods (Python and Go), call the validator before stage execution and fail fast with validation error before launching any activity.

---

### Task 3: Implement full stage-level parallelism and join semantics

**Files:**
- Modify: `kilvin-py/kilvin_py/workflows.py`
- Modify: `kilvin-go/workflows.go`

- [ ] **Step 1: Add branch outcome classifier and default max-parallelism behavior**

Python: replace `_parallel_capacity` so unset defaults to current pipeline count.

```python
def _parallel_capacity(strategy: PipelineStrategy | None, pipeline_count: int) -> int:
    if strategy is None or strategy.mode != "parallel":
        return 1
    if strategy.max_parallelism is None or strategy.max_parallelism <= 0:
        return max(1, pipeline_count)
    return max(1, strategy.max_parallelism)
```

Go: replace `parallelCapacity` implementation to return `len(pipelines)` when `max_parallelism` is nil/<=0.

- [ ] **Step 2: Add join behavior helper for Python**

In `kilvin-py/kilvin_py/workflows.py`, split pipeline scheduling into completion-aware collection and join policy handling.

```python
async def _await_pipeline_stage_results(results: list[workflow.Task], join_behavior: str, stage: StageConfig):
    if join_behavior == "fastest_success":
        first_error: Exception | None = None
        for completed in workflow.as_completed(results):
            try:
                out = await completed
                return [out], []
            except Exception as err:
                first_error = err if first_error is None else first_error
                if stage.pipeline_strategy and stage.pipeline_strategy.normalized_join_behavior() == "fastest_success":
                    continue
        if first_error:
            raise first_error
        return [], []

    completed = [await t for t in (await workflow.wait_condition(None),)]
    return completed, []
```

Use this helper to:
- keep all results for `all_required`
- ignore failures from skippable pipelines for `all_or_skip_failed`
- short-circuit on first success for `fastest_success` and stop awaiting nonessential tasks.

- [ ] **Step 3: Add join behavior helper for Go**

In `kilvin-go/workflows.go`, replace the simple `for _, pendingWorkflow := range pending { ... Get() ...}` pattern with a completion loop:

1. Start all child workflows with a bounded concurrency scheduler (`Channel` + worker goroutine loop or Temporal `workflow.NewBufferedChannel` + `workflow.Go`) respecting `maxParallel`.
2. Track monitor results and failed/required branch state.
3. For `fastest_success`, return stage success immediately after one successful `pipeline` terminal result and issue cancel requests for remaining child workflows.
4. For `all_or_skip_failed`, only propagate errors when pipeline profile is not `Skippable`.

Expected: run succeeds or fails exactly according to `join_behavior`.

- [ ] **Step 4: Add stage-level trace annotations for join reason**

Append one `StepExecutionEnvelope` trace entry per stage transition with `status` set from computed join outcome and `error` describing whether the stage short-circuited.

---

### Task 4: Enforce stage-level policy and timeout controls

**Files:**
- Modify: `kilvin-py/kilvin_py/workflows.py`
- Modify: `kilvin-go/workflows.go`
- Modify: `kilvin-py/tests/test_stage_policy.py` (create)
- Modify: `kilvin-go/workflows_policy_test.go` (create)

- [ ] **Step 1: Compute effective per-stage retry and timeout values**

In Python `_run_step`, change start-to-close timeout and retry policy to use normalized stage-level policy:

```python
effective_timeout = stage.stage_timeout_minutes if stage.stage_timeout_minutes is not None else input.run_config.policy.stage_timeout_minutes
retry_limit = stage.stage_retry if stage.stage_retry is not None else input.run_config.policy.max_stage_retries

attempt = await workflow.execute_activity(
    ...,
    start_to_close_timeout=timedelta(minutes=effective_timeout),
    retry_policy=workflow.RetryPolicy(maximum_attempts=max(1, retry_limit)),
)
```

Go equivalent in `runStep` wrappers: compute `attempts` and timeout from stage policy with run-level fallback.

- [ ] **Step 2: Add tests for fallback precedence and override**

Python test: one stage sets `stage_timeout_minutes=1` and run policy is 10; assert a step receives smaller timeout.

Go test: verify `ResolveStageRetryAttempts` and `ResolveStageTimeout` follow override-first semantics.

---

### Task 5: Add replay scope behavior and checksum bypass/override semantics

**Files:**
- Modify: `kilvin-py/kilvin_py/models.py`
- Modify: `kilvin-py/kilvin_py/workflows.py`
- Modify: `kilvin-go/models.go`
- Modify: `kilvin-go/workflows.go`
- Create: `kilvin-py/tests/test_replay_scope.py`
- Create: `kilvin-go/replay_test.go`

- [ ] **Step 1: Expand replay signal DTOs for `force` and `override_input_uri`**

Add fields in Python replay signal model and corresponding Go struct:

```python
@dataclass(frozen=True)
class ReplaySignal:
    target_stage_id: str
    target_pipeline_id: str | None = None
    target_step: str = ""
    scope: str = "step"
    force: bool = False
    override_input_uri: str | None = None
```

- [ ] **Step 2: Compute checksum-based skip with `force=false`**

In both runtimes, when deciding `_should_skip_for_replay`/`shouldSkipPipelineStep`, load existing `input_artifact` checksum from artifact record and compare to computed checksum of current input payload. Skip only when identical and `force` is false.

- [ ] **Step 3: Implement `scope=stage` as first-failed-step restart**

When replay target scope is `stage`, set replay cursor to first failed step in target stage and preserve downstream skip/cleanup state. Clear `replay_target` only after first matching failed step successfully re-executes.

- [ ] **Step 4: Apply `override_input_uri` in step skip and rerun logic**

For replayed steps with `override_input_uri`, use that artifact as canonical input and bypass old artifact checksum mismatch handling.

---

### Task 6: Make Go query surface match Python parity for inspection

**Files:**
- Modify: `kilvin-go/workflows.go`
- Modify: `kilvin-py/kilvin_py/workflows.py`
- Create: `docs/superpowers/plans/2026-04-11-kilvin-query-surface-verification.md` (if needed for API comparison)

- [ ] **Step 1: Add missing Go query handlers equivalent to Python**

In Go, add:

```go
func (w *TrainingWorkflow) QueryPlan() any { return ... }
func (w *TrainingWorkflow) QueryArtifacts() []StepIOArtifact { ... }
func (w *TrainingWorkflow) QueryRunArtifacts() []StepIOArtifact { ... }
```

Use the same struct shape fields as `run_plan`, `run_artifacts`, and `run_step_trace` in the Python implementation.

- [ ] **Step 2: Add filtering helpers**

Support `stage`, `pipeline_id`, and `step_name` filtering in query payload or helper methods so operators can inspect stage slices without dumping all data.

- [ ] **Step 3: Add contract test for parity payload shape**

Create `kilvin-go/query_contract_test.go` that checks JSON-marshaled keys include:
- `run_id`, `run_attempt`, `current_stage`, `current_step`, `current_pipeline`, `failures`, `stage_traces`
- `run_plan` stage+pipeline metadata when query is called.

---

### Task 7: Add CI-local validation gates and run smoke checks

**Files:**
- Modify: `kilvin-py/pyproject.toml`
- Create: `kilvin-py/tests/test_contract_smoke.py`
- Modify: `kilvin-go/go.mod` (no behavior change)
- Create: `kilvin-go/workflows_smoke_test.go`

- [ ] **Step 1: Add minimal smoke test command list for both languages**

Python file with a tiny deterministic fixture that constructs a valid 4-stage config and asserts:
- stage validation passes
- `parallel_capacity` default resolves to pipeline count when unset.

Go smoke test with the same structure in `testing` package using plain structs and direct `ValidateRunConfig` usage.

- [ ] **Step 2: Run Python smoke tests**

Run:

```bash
cd kilvin-py
python -m pytest -q tests/test_stage_validation.py tests/test_replay_scope.py tests/test_contract_smoke.py
```

Expected:
- all three tests pass with `1 passed`, `2 passed`, etc.

- [ ] **Step 3: Run Go tests**

Run:

```bash
cd kilvin-go
CGO_ENABLED=0 go test ./...
```

Expected:
- all tests in validation, policy, replay, and query packages pass.

---

### Task 8: Close loop with doc + plan alignment

**Files:**
- Modify: `docs/superpowers/specs/2026-04-11-kilvin-temporal-training-design.md`
- Modify: `docs/superpowers/plans/2026-04-11-kilvin-temporal-training-complete-implementation.md`

- [ ] **Step 1: Add progress and decision checkpoints in spec appendix**

Append a short “Implementation parity checklist” section with each contract item and explicit implementation location in `kilvin-py` and `kilvin-go`.

- [ ] **Step 2: Add a post-implementation validation pass**

Add an appendix block saying:
- stage validation implemented
- join_behavior behaviors aligned
- replay scope rules aligned
- Go and Python query parity achieved

- [ ] **Step 3: Re-open plan for self-review**

Scan for placeholders or unresolved TODOs in both this plan and the spec update before moving to implementation.
