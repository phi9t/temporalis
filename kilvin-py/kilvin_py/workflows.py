from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow

from . import activities
from .models import (
    AllocateResourcesInput,
    ArtifactWriteInput,
    CancelSignal,
    CheckpointOutput,
    ConfigureTrainingDataInput,
    DevPrepareInput,
    DevPrepareOutput,
    ExtractStageConfigInput,
    ExtractStageConfigOutput,
    ExtractWorkflowConfigInput,
    MaterializeTrainingBundleInput,
    PipelineAllocation,
    ReamAllocationOutput,
    MonitorOutput,
    MonitorTrainingInput,
    PauseAtStepSignal,
    PauseSignal,
    PipelineBundleOutput,
    PipelineConfig,
    PipelineStrategy,
    JoinBehavior,
    PipelinePriority,
    ParentRunOutput,
    PurgeInput,
    ReplaySignal,
    ResumeSignal,
    RunConfig,
    StageConfig,
    StageExecutionFailure,
    StartKilvinCommandInput,
    SubmitK8sInput,
    SubmitK8sOutput,
    StepExecutionEnvelope,
    TrainingWorkflowInput,
    KilvinRunState,
    DataConfigureOutput,
)


workflow.unsafe.imports_passed_through()

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


def _pipeline_profiles(stage: StageConfig) -> list[PipelineConfig]:
    if stage.pipelines:
        return stage.pipelines
    return [
        PipelineConfig(
            pipeline_id="default-pipeline",
            component_name="foundation_model",
            machine_type="h100-sxm",
            node_count=64,
            gpus_per_node=8,
            rank_size=512,
            resource_pool="foundation",
            stage_overrides={},
        )
    ]


def _normalize_stage_pipeline_strategy(stage: StageConfig) -> StageConfig:
    strategy = stage.pipeline_strategy
    if strategy is None:
        return stage
    normalized = strategy.normalized_join_behavior()
    if normalized == strategy.join_behavior:
        return stage
    return StageConfig(
        stage_id=stage.stage_id,
        stage_type=stage.stage_type,
        phase=stage.phase,
        enabled=stage.enabled,
        dataset_profile=stage.dataset_profile,
        runtime_profile=stage.runtime_profile,
        pipeline_strategy=PipelineStrategy(
            mode=strategy.mode,
            max_parallelism=strategy.max_parallelism,
            join_behavior=normalized,
        ),
        pipelines=stage.pipelines,
        stage_retry=stage.stage_retry,
        stage_timeout_minutes=stage.stage_timeout_minutes,
        depends_on=stage.depends_on,
    )


def _normalize_run_config(config: RunConfig) -> RunConfig:
    return RunConfig(
        run_id=config.run_id,
        kilvin_run_name=config.kilvin_run_name,
        workflow_spec=config.workflow_spec,
        policy=config.policy,
        stage_sequence=config.stage_sequence,
        stages=[_normalize_stage_pipeline_strategy(stage) for stage in config.stages],
        metadata=config.metadata,
    )


def _validate_run_config(config: RunConfig) -> None:
    if not config.stage_sequence:
        raise ValueError("stage_sequence must not be empty")
    if len(config.stages) == 0:
        raise ValueError("No stages configured")

    stage_by_id = {stage.stage_id: stage for stage in config.stages}
    unknown = [sid for sid in config.stage_sequence if sid not in stage_by_id]
    if unknown:
        raise ValueError(f"unknown stage_id in stage_sequence: {unknown}")
    for sid in config.stage_sequence:
        if sid not in ALLOWED_STAGE_IDS:
            raise ValueError(f"invalid stage_id in stage_sequence: {sid}")

    for sid in config.stage_sequence:
        if stage_by_id[sid].enabled is False:
            raise ValueError(f"stage {sid} in stage_sequence is disabled")

    stages = _ordered_stages(config)
    if not stages:
        raise ValueError("No enabled stages configured")

    seen = set[str]()
    for sid in config.stage_sequence:
        if sid in seen:
            raise ValueError(f"duplicate stage_id in stage_sequence: {sid}")
        seen.add(sid)

    foundation_ids = [sid for sid in config.stage_sequence if sid in FOUNDATION_SEQUENCE]
    expected = [sid for sid in FOUNDATION_SEQUENCE if sid in config.stage_sequence]
    if foundation_ids != expected:
        raise ValueError(
            "foundation stages must preserve vit/joint/continue/long_context order"
        )

    for stage in stages:
        if stage.phase == "foundation" and stage.stage_id not in FOUNDATION_SEQUENCE:
            raise ValueError(f"invalid foundation stage_id {stage.stage_id}")

    for stage in stages:
        for dep in stage.depends_on or []:
            if dep not in stage_by_id:
                raise ValueError(f"depends_on unknown stage {dep}")


def _ordered_stages(config: RunConfig) -> list[StageConfig]:
    stage_by_id = {stage.stage_id: stage for stage in config.stages}
    if config.stage_sequence:
        return [
            stage_by_id[sid]
            for sid in config.stage_sequence
            if sid in stage_by_id and stage_by_id[sid].enabled
        ]
    return [stage for stage in config.stages if stage.enabled]


def _parallel_capacity(strategy: PipelineStrategy | None) -> int:
    if strategy is None or strategy.mode != "parallel":
        return 1
    if strategy.max_parallelism is None or strategy.max_parallelism <= 0:
        return 0
    return strategy.max_parallelism


def _to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dict__"):
        try:
            return asdict(value)
        except Exception:
            return dict(value.__dict__)
    if isinstance(value, dict):
        return value
    return {"value": value}


def _should_fail_pipeline(status: str) -> bool:
    normalized = status.upper()
    return normalized not in {"SUCCESS", "SUCCEEDED", "OK"}


def _pipeline_join_behavior(stage: StageConfig) -> str:
    if stage.pipeline_strategy is None:
        return JoinBehavior.ALL_REQUIRED.value
    return stage.pipeline_strategy.normalized_join_behavior()


def _pipeline_should_ignore_failure(join_behavior: str, stage: StageConfig, pipeline: PipelineConfig) -> bool:
    if join_behavior != JoinBehavior.ALL_OR_SKIP_FAILED.value:
        return False
    if pipeline.skippable:
        return True
    if pipeline.priority == PipelinePriority.OPTIONAL:
        return True
    if pipeline.priority == PipelinePriority.PROBE:
        return True
    return False


def _pipeline_is_required(pipeline: PipelineConfig) -> bool:
    if pipeline.skippable:
        return False
    priority = pipeline.priority.value if isinstance(pipeline.priority, PipelinePriority) else str(pipeline.priority)
    return priority == PipelinePriority.REQUIRED.value


def _effective_stage_retry(stage: StageConfig, policy) -> int:
    if stage.stage_retry is not None and stage.stage_retry > 0:
        return stage.stage_retry
    return max(1, policy.max_stage_retries)


def _effective_timeout_seconds(stage: StageConfig, base_seconds: int) -> int:
    if stage.stage_timeout_minutes and stage.stage_timeout_minutes > 0:
        stage_limit = max(1, stage.stage_timeout_minutes * 60)
        return min(base_seconds, stage_limit)
    return base_seconds


def _matches_pipeline(target_pipeline_id: str | None, step_pipeline_id: str | None) -> bool:
    if target_pipeline_id is None:
        return True
    return target_pipeline_id == step_pipeline_id


@workflow.defn
class ParentCmdWorkflow:
    def __init__(self) -> None:
        self._state = "PENDING"
        self._cancelled = False

    @workflow.signal
    def cancel(self, _input: CancelSignal | None = None) -> None:
        self._state = "CANCELLED"
        self._cancelled = True

    @workflow.run
    async def run(self, input: StartKilvinCommandInput) -> ParentRunOutput:
        ir_name = f"kilvin-ir-{input.run_config.run_id}"
        try:
            extracted = await workflow.execute_activity(
                activities.extract_cmd_config,
                ExtractCmdConfigInput(
                    run_config=input.run_config,
                    cmd_name=input.cmd_name,
                    job_params_uri=input.job_params_uri,
                ),
                start_to_close_timeout=timedelta(seconds=30),
            )

            child_input = TrainingWorkflowInput(
                run_id=input.run_config.run_id,
                run_config=input.run_config,
                extracted=extracted,
            )

            await workflow.execute_child_workflow(
                TrainingWorkflow.run,
                child_input,
                id=f"kilvin-training-{input.run_config.run_id}",
                task_queue="kilvin-training-task-queue",
                retry_policy=workflow.RetryPolicy(maximum_attempts=2),
            )

            if self._cancelled:
                await workflow.execute_activity(
                    activities.update_cmd_state,
                    {
                        "run_id": input.run_config.run_id,
                        "final_state": "KILVIN_CANCELLED",
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
                raise RuntimeError("parent workflow cancelled")

            await workflow.execute_activity(
                activities.update_cmd_state,
                {
                    "run_id": input.run_config.run_id,
                    "final_state": "KILVIN_SUCCESS",
                    "ir_name": ir_name,
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            self._state = "SUCCEEDED"
            return ParentRunOutput(
                run_id=input.run_config.run_id,
                final_state="KILVIN_SUCCESS",
                ir_name=ir_name,
            )
        except Exception as err:  # pragma: no cover - orchestration path
            self._state = "FAILED"
            await workflow.execute_activity(
                activities.update_cmd_state,
                {
                    "run_id": input.run_config.run_id,
                    "final_state": "KILVIN_FAILED",
                    "error": str(err),
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            raise


@workflow.defn
class TrainingWorkflow:
    def __init__(self) -> None:
        self.state = "RUNNING"
        self._run_attempt = 0
        self._step_traces: list[StepExecutionEnvelope] = []
        self._failures: list[StageExecutionFailure] = []
        self._paused = False
        self._pause_filter: PauseAtStepSignal | None = None
        self._cancelled = False
        self._replay_target: ReplaySignal | None = None
        self._replay_step_waiting = False
        self._current_step: tuple[str, str | None, str] | None = None
        self._run_id = ""
        self._run_config: RunConfig | None = None


@dataclass(frozen=True)
class PipelineTaskResult:
    pipeline_id: str
    submit_output: SubmitK8sOutput | None
    monitor_output: MonitorOutput | None
    error: Exception | None

    @workflow.query
    def run_status(self) -> KilvinRunState:
        current_stage = self._current_step[0] if self._current_step else ""
        current_pipeline = self._current_step[1] if self._current_step else None
        current_step = self._current_step[2] if self._current_step else None
        return KilvinRunState(
            run_id=self._run_id,
            run_attempt=self._run_attempt,
            current_stage=current_stage,
            current_pipeline=current_pipeline,
            current_step=current_step,
            overall_status=self.state,
            paused=self._paused,
            stage_traces=self._step_traces,
            failures=self._failures,
        )

    @workflow.query
    def run_step_trace(self) -> list[StepExecutionEnvelope]:
        return list(self._step_traces)

    @workflow.query
    def run_artifacts(self) -> list[str]:
        uris: list[str] = []
        for entry in self._step_traces:
            uris.append(entry.input_artifact.uri)
            if entry.output_artifact:
                uris.append(entry.output_artifact.uri)
        return uris

    @workflow.query
    def run_plan(self) -> list[str]:
        return [stage.stage_id for stage in _ordered_stages(_normalize_run_config)]

    @workflow.signal
    def pause(self, _input: PauseSignal | None = None) -> None:
        self._paused = True
        self.state = "PAUSED"

    @workflow.signal
    def resume(self, _input: ResumeSignal | None = None) -> None:
        self._paused = False
        if self.state == "PAUSED":
            self.state = "RUNNING"

    @workflow.signal
    def pause_at_step(self, signal: PauseAtStepSignal) -> None:
        self._pause_filter = signal

    @workflow.signal
    def replay_step(self, signal: ReplaySignal) -> None:
        self._run_attempt += 1
        self._replay_target = signal
        self._replay_step_waiting = signal.scope == "step"
        self._paused = False
        self.state = "RUNNING"

    @workflow.signal
    def cancel(self, _input: CancelSignal | None = None) -> None:
        self._cancelled = True
        self.state = "CANCELLED"

    def _lookup_replay_stage_index(self, stages: list[StageConfig]) -> int | None:
        if not self._replay_target:
            return None
        for idx, stage in enumerate(stages):
            if stage.stage_id == self._replay_target.target_stage_id:
                return idx
        return None

    def _should_skip_for_replay(
        self,
        stages: list[StageConfig],
        stage_index: int,
        stage: StageConfig,
        pipeline_id: str | None,
        step_name: str,
    ) -> bool:
        if not self._replay_target:
            return False
        target = self._replay_target
        target_stage_index = self._lookup_replay_stage_index(stages)
        if target_stage_index is None:
            return False
        if stage_index > target_stage_index:
            return False
        if stage_index < target_stage_index:
            return True

        # stage_index == target_stage_index
        if target.scope == "stage":
            return False

        if target.scope == "pipeline":
            if pipeline_id is None:
                return False
            return not _matches_pipeline(target.target_pipeline_id, pipeline_id)

        # target.scope == "step"
        if self._replay_step_waiting is False:
            return False
        if target.target_step != step_name:
            if target.target_pipeline_id is None:
                if pipeline_id is not None:
                    return True
                return True
            if pipeline_id is None:
                return False
            return not _matches_pipeline(target.target_pipeline_id, pipeline_id)
        if target.target_pipeline_id is not None and not _matches_pipeline(
            target.target_pipeline_id,
            pipeline_id,
        ):
            return True
        self._replay_step_waiting = False
        self._replay_target = None
        return False

    def _append_step_trace(
        self,
        run_id: str,
        stage: StageConfig,
        stage_index: int,
        pipeline_id: str | None,
        pipeline_index: int | None,
        step_name: str,
        status: str,
        input_artifact,
        input_checksum: str,
        output_artifact=None,
        error: str | None = None,
        started_at_ms: int | None = None,
        completed_at_ms: int | None = None,
    ) -> None:
        self._step_traces.append(
            StepExecutionEnvelope(
                run_id=run_id,
                run_attempt=self._run_attempt,
                stage_id=stage.stage_id,
                stage_index=stage_index,
                step_name=step_name,
                pipeline_id=pipeline_id,
                pipeline_index=pipeline_index,
                status=status,
                retry_attempt=0,
                input_artifact=input_artifact,
                output_artifact=output_artifact,
                error=error,
                input_checksum=input_checksum,
                output_checksum=output_artifact.checksum_sha256 if output_artifact else None,
                started_at_ms=started_at_ms,
                completed_at_ms=completed_at_ms,
            )
        )

    async def _persist_step_artifact(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        pipeline_id: str | None,
        pipeline_index: int | None,
        step_name: str,
        payload: Any,
    ) -> Any:
        artifact = await workflow.execute_activity(
            activities.persist_yaml_artifact,
            ArtifactWriteInput(
                run_id=input.run_config.run_id,
                run_attempt=self._run_attempt,
                artifact_name=f"{stage.stage_id}/{pipeline_id or 'default'}/{step_name}/in.yaml",
                payload=_to_dict(payload),
            ),
            start_to_close_timeout=timedelta(seconds=20),
        )

        return StepExecutionEnvelope(
            run_id=input.run_config.run_id,
            run_attempt=self._run_attempt,
            stage_id=stage.stage_id,
            stage_index=stage_index,
            step_name=step_name,
            pipeline_id=pipeline_id,
            pipeline_index=pipeline_index,
            status="QUEUED",
            retry_attempt=0,
            input_artifact=artifact,
            input_checksum=artifact.checksum_sha256,
            started_at_ms=int(workflow.now().timestamp() * 1000),
        )

    async def _record_skipped_step(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        pipeline_id: str | None,
        pipeline_index: int | None,
        step_name: str,
        payload: Any,
        reason: str,
    ) -> None:
        envelope = await self._persist_step_artifact(
            input=input,
            stage=stage,
            stage_index=stage_index,
            pipeline_id=pipeline_id,
            pipeline_index=pipeline_index,
            step_name=step_name,
            payload=_to_dict(
                {
                    "step_name": step_name,
                    "stage_id": stage.stage_id,
                    "pipeline_id": pipeline_id,
                    "pipeline_index": pipeline_index,
                    "run_id": input.run_config.run_id,
                    "run_attempt": self._run_attempt,
                    "replay_skip": True,
                    "reason": reason,
                    "payload": _to_dict(payload),
                }
            ),
        )
        self._append_step_trace(
            run_id=input.run_config.run_id,
            stage=stage,
            stage_index=stage_index,
            pipeline_id=pipeline_id,
            pipeline_index=pipeline_index,
            step_name=step_name,
            status="SKIPPED",
            input_artifact=envelope.input_artifact,
            input_checksum=envelope.input_checksum,
            error=reason,
            started_at_ms=envelope.started_at_ms,
            completed_at_ms=int(workflow.now().timestamp() * 1000),
        )

    async def _run_step(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        pipeline_id: str | None,
        pipeline_index: int | None,
        step_name: str,
        activity_fn,
        activity_input: Any,
        timeout_seconds: int = 120,
        retry_attempts: int | None = None,
        skip_result: Any | None = None,
    ) -> Any:
        if self._cancelled:
            raise RuntimeError("training workflow cancelled")

        if self._pause_filter and self._pause_filter.when == "pre":
            if self._pause_filter.stage_id == stage.stage_id and (
                self._pause_filter.pipeline_id is None or self._pause_filter.pipeline_id == pipeline_id
            ) and self._pause_filter.step_name == step_name:
                self._paused = True

        if self._paused:
            self.state = "PAUSED"
            await workflow.wait_condition(lambda: not self._paused)
            self.state = "RUNNING"

        stages = _ordered_stages(input.run_config)
        if self._should_skip_for_replay(
            stages=stages,
            stage_index=stage_index,
            stage=stage,
            pipeline_id=pipeline_id,
            step_name=step_name,
        ):
            await self._record_skipped_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                pipeline_id=pipeline_id,
                pipeline_index=pipeline_index,
                step_name=step_name,
                payload=activity_input,
                reason=f"skipped for replay scope={self._replay_target.scope if self._replay_target else 'none'}",
            )
            return skip_result

        envelope = await self._persist_step_artifact(input, stage, stage_index, pipeline_id, pipeline_index, step_name, {
            "step_name": step_name,
            "stage_id": stage.stage_id,
            "pipeline_id": pipeline_id,
            "pipeline_index": pipeline_index,
            "run_id": input.run_config.run_id,
            "run_attempt": self._run_attempt,
            "payload": _to_dict(activity_input),
        })
        self._current_step = (stage.stage_id, pipeline_id, step_name)
        self._append_step_trace(
            run_id=input.run_config.run_id,
            stage=stage,
            stage_index=stage_index,
            pipeline_id=pipeline_id,
            pipeline_index=pipeline_index,
            step_name=step_name,
            status="RUNNING",
            input_artifact=envelope.input_artifact,
            input_checksum=envelope.input_checksum,
            started_at_ms=envelope.started_at_ms,
        )

        try:
            output = await workflow.execute_activity(
                activity_fn,
                activity_input,
                start_to_close_timeout=timedelta(seconds=timeout_seconds),
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=retry_attempts or 3,
                    initial_interval=timedelta(seconds=5),
                ),
            )

            output_artifact = await workflow.execute_activity(
                activities.persist_yaml_artifact,
                ArtifactWriteInput(
                    run_id=input.run_config.run_id,
                    run_attempt=self._run_attempt,
                    artifact_name=f"{stage.stage_id}/{pipeline_id or 'default'}/{step_name}/out.yaml",
                    payload=_to_dict(output),
                ),
                start_to_close_timeout=timedelta(seconds=20),
            )
            self._append_step_trace(
                run_id=input.run_config.run_id,
                stage=stage,
                stage_index=stage_index,
                step_name=step_name,
                pipeline_id=pipeline_id,
                pipeline_index=pipeline_index,
                status="SUCCEEDED",
                input_artifact=envelope.input_artifact,
                output_artifact=output_artifact,
                input_checksum=envelope.input_checksum,
                error=None,
                started_at_ms=envelope.started_at_ms,
                completed_at_ms=int(workflow.now().timestamp() * 1000),
            )
            return output

        except Exception as err:
            self._failures.append(
                StageExecutionFailure(
                    stage_id=stage.stage_id,
                    pipeline_id=pipeline_id,
                    step_name=step_name,
                    attempt=self._run_attempt,
                    error=str(err),
                )
            )
            self._append_step_trace(
                run_id=input.run_config.run_id,
                stage=stage,
                stage_index=stage_index,
                step_name=step_name,
                pipeline_id=pipeline_id,
                pipeline_index=pipeline_index,
                status="FAILED",
                input_artifact=envelope.input_artifact,
                input_checksum=envelope.input_checksum,
                error=str(err),
                started_at_ms=envelope.started_at_ms,
                completed_at_ms=int(workflow.now().timestamp() * 1000),
            )
            raise

    async def _run_pipeline(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        bundle: PipelineBundleOutput,
        bundle_name: str,
    ) -> tuple[SubmitK8sOutput, MonitorOutput]:
        submit_out = await self._run_step(
            input=input,
            stage=stage,
            stage_index=stage_index,
            pipeline_id=bundle.pipeline_id,
            pipeline_index=None,
            step_name="submit_k8s_job",
            activity_fn=activities.submit_k8s_job,
            activity_input=SubmitK8sInput(
                pipeline_id=bundle.pipeline_id,
                bundle=bundle.bundle,
                namespace="kilvin-training",
            ),
            timeout_seconds=180,
            skip_result=SubmitK8sOutput(
                auto_job_name=f"replay-skip-{bundle.pipeline_id}",
                primus_job_id="skip-replay",
                primus_ui_url="skipped://monitor",
                k8s_namespace="kilvin-training",
            ),
        )

        monitor_out = await self._run_step(
            input=input,
            stage=stage,
            stage_index=stage_index,
            pipeline_id=bundle.pipeline_id,
            pipeline_index=None,
            step_name="monitor_training",
            activity_fn=activities.monitor_training,
            activity_input=MonitorTrainingInput(
                pipeline_id=bundle.pipeline_id,
                auto_job_name=submit_out.auto_job_name,
                primus_job_id=submit_out.primus_job_id,
                ir_name=bundle_name,
                k8s_namespace=submit_out.k8s_namespace,
            ),
            timeout_seconds=3600,
            skip_result=MonitorOutput(final_status="SUCCEEDED"),
        )
        return submit_out, monitor_out

    @workflow.run
    async def run(self, input: TrainingWorkflowInput) -> str:
        self._run_id = input.run_config.run_id
        self._run_attempt += 1

        stages = _ordered_stages(input.run_config)
        if not stages:
            raise RuntimeError(f"No enabled stages configured for {self._run_id}")

        dev_prepare = await self._run_step(
            input=input,
            stage=stages[0],
            stage_index=0,
            pipeline_id=None,
            pipeline_index=None,
            step_name="dev_prepare",
            activity_fn=activities.dev_prepare,
            activity_input=DevPrepareInput(
                run_id=input.run_config.run_id,
                checkpoint=input.extracted.checkpoint,
            ),
            timeout_seconds=120,
            skip_result=DevPrepareOutput(
                auto_job_id=f"kilvin-replay-{self._run_attempt}",
                code_tos_key=input.extracted.checkpoint or "s3://models/k2/checkpoint",
            ),
        )

        checkpoint = await self._run_step(
            input=input,
            stage=stages[0],
            stage_index=0,
            pipeline_id=None,
            pipeline_index=None,
            step_name="validate_checkpoint",
            activity_fn=activities.validate_checkpoint,
            activity_input=dev_prepare.code_tos_key,
            timeout_seconds=120,
            skip_result=CheckpointOutput(
                checkpoint_path=input.extracted.checkpoint or "s3://models/k2/checkpoint",
                manifest_uri="file://./.kilvin-artifacts/skip/manifest.yaml",
                model_size_estimate=700_000_000_000,
            ),
        )

        current_checkpoint = checkpoint.checkpoint_path
        for stage_index, stage in enumerate(stages):
            if self._cancelled:
                break

            configure_out = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                pipeline_id=None,
                pipeline_index=None,
                step_name="configure_training_data",
                activity_fn=activities.configure_training_data,
                activity_input=ConfigureTrainingDataInput(
                    dataset_uri=stage.dataset_profile.uri,
                    dataset_stage=stage.stage_id,
                    required_token_budget=stage.runtime_profile.total_tokens_target,
                    min_examples=stage.dataset_profile.min_examples,
                    token_budget_tolerance_ratio=stage.dataset_profile.token_budget_tolerance_ratio,
                    data_mix_requirements=stage.dataset_profile.mix_requirements,
                    quality_thresholds=stage.dataset_profile.quality_thresholds,
                ),
                timeout_seconds=120,
                skip_result=DataConfigureOutput(
                    dataset_id=f"skip-{stage.stage_id}",
                    schema_version="skip",
                    shard_count=0,
                    estimated_tokens=stage.runtime_profile.total_tokens_target,
                    stage_token_mix={"skipped": 1},
                    composition_breakdown={"skipped": 1.0},
                    quality_scores={"skipped": 1.0},
                    total_examples=0,
                ),
            )

            allocation = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                pipeline_id=None,
                pipeline_index=None,
                step_name="allocate_resources",
                activity_fn=activities.allocate_resources,
                activity_input=AllocateResourcesInput(
                    run_id=input.run_config.run_id,
                    stage_id=stage.stage_id,
                    stage_index=stage_index,
                    pipeline_profiles=_pipeline_profiles(stage),
                ),
                timeout_seconds=180,
                skip_result=ReamAllocationOutput(
                    allocation_id=f"skip-allocation-{stage.stage_id}",
                    resource_epoch=0,
                    pools_reservation_id="skip",
                    pipeline_allocations=[
                        PipelineAllocation(
                            pipeline_id="default-pipeline",
                            component_name="foundation_model",
                            node_count=1,
                            gpus_per_node=1,
                            rank_size=1,
                            machine_type="h100-sxm",
                            pool_name="foundation",
                        )
                    ],
                ),
            )

            materialization_tasks = []
            pipeline_profiles = _pipeline_profiles(stage)
            for pipeline_index, profile in enumerate(pipeline_profiles):
                materialization_input = MaterializeTrainingBundleInput(
                    ir_name=f"kilvin-ir-{input.run_config.run_id}-{stage.stage_id}",
                    checkpoint=current_checkpoint,
                    config_snapshot=input.extracted.workflow_config_uri,
                    pipeline_id=profile.pipeline_id,
                    allocation=next(
                        (a for a in allocation.pipeline_allocations if a.pipeline_id == profile.pipeline_id),
                        allocation.pipeline_allocations[0],
                    ),
                    pipeline_profile=profile,
                    stage_index=stage_index,
                    train_stage=stage.stage_id,
                    task_type="foundation_train",
                    total_tokens_target=stage.runtime_profile.total_tokens_target,
                    global_batch_tokens=stage.runtime_profile.global_batch_tokens,
                    max_steps=stage.runtime_profile.max_steps,
                    learning_rate=stage.runtime_profile.learning_rate,
                    model=input.extracted.component_profile.get("model", "kilvin-base"),
                )
                materialization_tasks.append(
                    self._run_step(
                        input=input,
                        stage=stage,
                        stage_index=stage_index,
                        pipeline_id=profile.pipeline_id,
                        pipeline_index=pipeline_index,
                        step_name="materialize_training_bundle",
                        activity_fn=activities.materialize_training_bundle,
                        activity_input=materialization_input,
                        timeout_seconds=180,
                        skip_result=PipelineBundleOutput(
                            pipeline_id=profile.pipeline_id,
                            bundle=None,  # type: ignore[call-arg]
                        ),
                    )
                )

            if _parallel_capacity(stage.pipeline_strategy) > 1:
                bundle_outputs = []
                async for completed in workflow.as_completed(materialization_tasks):
                    bundle_outputs.append(await completed)
            else:
                bundle_outputs = [await t for t in materialization_tasks]

            pipeline_tasks = [
                self._run_pipeline(
                    input=input,
                    stage=stage,
                    stage_index=stage_index,
                    bundle=bundle,
                    bundle_name=f"kilvin-ir-{input.run_config.run_id}-{stage.stage_id}",
                )
                for bundle in bundle_outputs
            ]

            if _parallel_capacity(stage.pipeline_strategy) > 1:
                pipeline_results = []
                async for completed in workflow.as_completed(pipeline_tasks):
                    pipeline_results.append(await completed)
            else:
                pipeline_results = [await t for t in pipeline_tasks]

            for submit_out, monitor_out in pipeline_results:
                if _should_fail_pipeline(monitor_out.final_status):
                    raise RuntimeError(
                        f"pipeline failed for {submit_out.auto_job_name}: {monitor_out.final_status}"
                    )

            await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                pipeline_id=None,
                pipeline_index=None,
                step_name="purge_resources",
                activity_fn=activities.purge_resources,
                activity_input=PurgeInput(
                    run_id=input.run_config.run_id,
                    stage_id=stage.stage_id,
                    preserve_artifacts=input.run_config.policy.preserve_artifacts_on_failure,
                    checkpoint=current_checkpoint,
                ),
                timeout_seconds=180,
            )

            current_checkpoint = f"{current_checkpoint}/{stage.stage_id}"

            if self._replay_target and self._replay_target.scope == "step" and self._replay_target.target_stage_id == stage.stage_id:
                self._replay_target = None

        self.state = "COMPLETED"
        return f"KILVIN_TRAINING_COMPLETED:{input.run_config.run_id}"
