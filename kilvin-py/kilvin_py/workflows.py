from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from . import activities

from .models import (
    AllocateResourcesInput,
    ArtifactWriteInput,
    CancelSignal,
    DevPrepareInput,
    DevPrepareOutput,
    ExtractCmdConfigInput,
    KilvinRunState,
    MaterializedBundleOutput,
    MaterializeTrainingBundleInput,
    MonitorOutput,
    MonitorTrainingInput,
    ParentRunOutput,
    PauseAtStepSignal,
    PauseSignal,
    ReamAllocationOutput,
    ReplaySignal,
    ResumeSignal,
    RunConfig,
    StageConfig,
    StageExecutionFailure,
    StartKilvinCommandInput,
    StepExecutionEnvelope,
    SubmitK8sInput,
    SubmitK8sOutput,
    TrainingWorkflowInput,
)

ALLOWED_STAGE_IDS = {"pretrain", "sft", "rl"}


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

    if "pretrain" in config.stage_sequence and config.stage_sequence[0] != "pretrain":
        raise ValueError("pretrain must run before fine-tuning stages")

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


def _to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dict__"):
        try:
            return asdict(value)
        except Exception:
            return dict(value.__dict__)
    if isinstance(value, dict):
        return value
    return {"value": value}


def _is_failed_status(status: str) -> bool:
    normalized = status.upper()
    return normalized not in {"SUCCESS", "SUCCEEDED", "OK"}


@workflow.defn
class ParentKilvinCmdWorkflow:
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
                KilvinTrainingWorkflow.run,
                child_input,
                id=f"kilvin-training-{input.run_config.run_id}",
                task_queue="kilvin-training-task-queue",
                retry_policy=RetryPolicy(maximum_attempts=2),
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
                raise ApplicationError("parent workflow cancelled", non_retryable=True)

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
class KilvinTrainingWorkflow:
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
        self._current_step: tuple[str, str] | None = None
        self._run_id = ""
        self._run_config: RunConfig | None = None
        self._named_artifact_uris: list[str] = []

    @workflow.query
    def run_status(self) -> KilvinRunState:
        current_stage = self._current_step[0] if self._current_step else ""
        current_step = self._current_step[1] if self._current_step else None
        return KilvinRunState(
            run_id=self._run_id,
            run_attempt=self._run_attempt,
            current_stage=current_stage,
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
        uris.extend(self._named_artifact_uris)
        return uris

    @workflow.query
    def run_plan(self) -> list[str]:
        if self._run_config is None:
            return []
        return [stage.stage_id for stage in _ordered_stages(self._run_config)]

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
        self._paused = False
        self._pause_filter = None
        self.state = "CANCELLED"

    def _should_pause_at(self, stage: StageConfig, step_name: str, when: str) -> bool:
        if self._pause_filter is None:
            return False
        return (
            self._pause_filter.when == when
            and self._pause_filter.stage_id == stage.stage_id
            and self._pause_filter.step_name == step_name
        )

    async def _wait_while_paused(self) -> None:
        if not self._paused:
            return
        self.state = "PAUSED"
        await workflow.wait_condition(lambda: not self._paused)
        if self._cancelled:
            raise ApplicationError("training workflow cancelled", non_retryable=True)
        self.state = "RUNNING"

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

        # target.scope == "step"
        if self._replay_step_waiting is False:
            return False
        if target.target_step != step_name:
            return True
        self._replay_step_waiting = False
        self._replay_target = None
        return False

    def _append_step_trace(
        self,
        run_id: str,
        stage: StageConfig,
        stage_index: int,
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
        step_name: str,
        payload: Any,
    ) -> StepExecutionEnvelope:
        artifact = await workflow.execute_activity(
            activities.persist_yaml_artifact,
            ArtifactWriteInput(
                run_id=input.run_config.run_id,
                run_attempt=self._run_attempt,
                artifact_name=f"{stage.stage_id}/{step_name}/in.yaml",
                payload=_to_dict(payload),
            ),
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        return StepExecutionEnvelope(
            run_id=input.run_config.run_id,
            run_attempt=self._run_attempt,
            stage_id=stage.stage_id,
            stage_index=stage_index,
            step_name=step_name,
            status="QUEUED",
            retry_attempt=0,
            input_artifact=artifact,
            input_checksum=artifact.checksum_sha256,
            started_at_ms=int(workflow.now().timestamp() * 1000),
        )

    async def _persist_named_artifact(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        step_name: str,
        artifact_label: str,
        payload: Any,
    ) -> None:
        """Persist a hood-open artifact (quota decision, env vars, logs) beside the step record."""

        artifact = await workflow.execute_activity(
            activities.persist_yaml_artifact,
            ArtifactWriteInput(
                run_id=input.run_config.run_id,
                run_attempt=self._run_attempt,
                artifact_name=f"{stage.stage_id}/{step_name}/{artifact_label}.yaml",
                payload=_to_dict(payload),
            ),
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._named_artifact_uris.append(artifact.uri)

    async def _record_skipped_step(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        step_name: str,
        payload: Any,
        reason: str,
    ) -> None:
        envelope = await self._persist_step_artifact(
            input=input,
            stage=stage,
            stage_index=stage_index,
            step_name=step_name,
            payload=_to_dict(
                {
                    "step_name": step_name,
                    "stage_id": stage.stage_id,
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
        step_name: str,
        activity_fn,
        activity_input: Any,
        timeout_seconds: int = 120,
        retry_attempts: int | None = None,
        skip_result: Any | None = None,
    ) -> Any:
        if self._cancelled:
            raise ApplicationError("training workflow cancelled", non_retryable=True)

        if self._should_pause_at(stage, step_name, "pre"):
            self._paused = True
            self._pause_filter = None

        await self._wait_while_paused()

        stages = _ordered_stages(input.run_config)
        if self._should_skip_for_replay(
            stages=stages,
            stage_index=stage_index,
            step_name=step_name,
        ):
            await self._record_skipped_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name=step_name,
                payload=activity_input,
                reason=f"skipped for replay scope={self._replay_target.scope if self._replay_target else 'none'}",
            )
            return skip_result

        envelope = await self._persist_step_artifact(input, stage, stage_index, step_name, {
            "step_name": step_name,
            "stage_id": stage.stage_id,
            "run_id": input.run_config.run_id,
            "run_attempt": self._run_attempt,
            "payload": _to_dict(activity_input),
        })
        self._current_step = (stage.stage_id, step_name)
        self._append_step_trace(
            run_id=input.run_config.run_id,
            stage=stage,
            stage_index=stage_index,
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
                retry_policy=RetryPolicy(
                    maximum_attempts=retry_attempts or 3,
                    initial_interval=timedelta(seconds=5),
                ),
            )

            output_artifact = await workflow.execute_activity(
                activities.persist_yaml_artifact,
                ArtifactWriteInput(
                    run_id=input.run_config.run_id,
                    run_attempt=self._run_attempt,
                    artifact_name=f"{stage.stage_id}/{step_name}/out.yaml",
                    payload=_to_dict(output),
                ),
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            self._append_step_trace(
                run_id=input.run_config.run_id,
                stage=stage,
                stage_index=stage_index,
                step_name=step_name,
                status="SUCCEEDED",
                input_artifact=envelope.input_artifact,
                output_artifact=output_artifact,
                input_checksum=envelope.input_checksum,
                error=None,
                started_at_ms=envelope.started_at_ms,
                completed_at_ms=int(workflow.now().timestamp() * 1000),
            )
            if self._should_pause_at(stage, step_name, "post"):
                self._paused = True
                self._pause_filter = None
            await self._wait_while_paused()
            return output

        except Exception as err:
            self._failures.append(
                StageExecutionFailure(
                    stage_id=stage.stage_id,
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
                status="FAILED",
                input_artifact=envelope.input_artifact,
                input_checksum=envelope.input_checksum,
                error=str(err),
                started_at_ms=envelope.started_at_ms,
                completed_at_ms=int(workflow.now().timestamp() * 1000),
            )
            raise

    @workflow.run
    async def run(self, input: TrainingWorkflowInput) -> str:
        self._run_id = input.run_config.run_id
        self._run_config = input.run_config
        self._run_attempt += 1

        try:
            _validate_run_config(input.run_config)
        except ValueError as err:
            raise ApplicationError(str(err), non_retryable=True) from err
        stages = _ordered_stages(input.run_config)
        if not stages:
            raise ApplicationError(
                f"No enabled stages configured for {self._run_id}", non_retryable=True
            )

        dev_prepare = await self._run_step(
            input=input,
            stage=stages[0],
            stage_index=0,
            step_name="dev_prepare",
            activity_fn=activities.dev_prepare,
            activity_input=DevPrepareInput(
                run_id=input.run_config.run_id,
                checkpoint=input.extracted.checkpoint,
            ),
            timeout_seconds=120,
            skip_result=DevPrepareOutput(
                auto_job_id=f"kilvin-replay-{self._run_attempt}",
                code_tos_key=input.extracted.checkpoint or "s3://checkpoints/model-x",
            ),
        )

        checkpoint = input.extracted.checkpoint or dev_prepare.code_tos_key
        ir_name = f"kilvin-ir-{input.run_config.run_id}"

        for stage_index, stage in enumerate(stages):
            if self._cancelled:
                break

            allocation = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="allocate_resources",
                activity_fn=activities.allocate_resources,
                activity_input=AllocateResourcesInput(
                    run_id=input.run_config.run_id,
                    stage_id=stage.stage_id,
                    stage_index=stage_index,
                    dataset_uri=stage.dataset_profile.uri,
                ),
                timeout_seconds=180,
                skip_result=ReamAllocationOutput(
                    allocation_id=f"skip-allocation-{stage.stage_id}",
                    resource_epoch=0,
                    pools_reservation_id="skip",
                    machine_type="a100-sxm",
                    pool_name="foundation",
                    node_count=1,
                    gpus_per_node=1,
                    rank_size=1,
                ),
            )

            if allocation.quota_decision is not None:
                await self._persist_named_artifact(
                    input=input,
                    stage=stage,
                    step_name="allocate_resources",
                    artifact_label="quota_decision",
                    payload=allocation.quota_decision,
                )

            bundle = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="materialize_training_bundle",
                activity_fn=activities.materialize_training_bundle,
                activity_input=MaterializeTrainingBundleInput(
                    ir_name=f"{ir_name}-{stage.stage_id}",
                    checkpoint=checkpoint,
                    config_snapshot=input.extracted.workflow_config_uri,
                    allocation=allocation,
                    stage_index=stage_index,
                    train_stage=stage.stage_id,
                    task_type="train",
                    total_tokens_target=stage.runtime_profile.total_tokens_target,
                    global_batch_tokens=stage.runtime_profile.global_batch_tokens,
                    max_steps=stage.runtime_profile.max_steps,
                    learning_rate=stage.runtime_profile.learning_rate,
                    model=input.extracted.component_profile.get("model", "model-x"),
                ),
                timeout_seconds=180,
                skip_result=MaterializedBundleOutput(
                    bundle_id=f"skip-bundle-{stage.stage_id}",
                    bundle_path="skipped://bundle",
                    bound_components=[],
                    runtime_setup={},
                    env_vars={},
                    rendezvous={},
                    launch_plan=[],
                    token_plan={},
                    health_checks=[],
                ),
            )

            if bundle.env_vars:
                await self._persist_named_artifact(
                    input=input,
                    stage=stage,
                    step_name="materialize_training_bundle",
                    artifact_label="env_vars",
                    payload=bundle.env_vars,
                )

            submit_out = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="submit_k8s_job",
                activity_fn=activities.submit_k8s_job,
                activity_input=SubmitK8sInput(
                    stage_id=stage.stage_id,
                    bundle=bundle,
                    namespace="kilvin-training",
                ),
                timeout_seconds=180,
                skip_result=SubmitK8sOutput(
                    auto_job_name=f"replay-skip-{stage.stage_id}",
                    primus_job_id="skip-replay",
                    primus_ui_url="skipped://monitor",
                    k8s_namespace="kilvin-training",
                ),
            )

            monitor_out = await self._run_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name="monitor_training",
                activity_fn=activities.monitor_training,
                activity_input=MonitorTrainingInput(
                    auto_job_name=submit_out.auto_job_name,
                    primus_job_id=submit_out.primus_job_id,
                    ir_name=f"{ir_name}-{stage.stage_id}",
                    k8s_namespace=submit_out.k8s_namespace,
                ),
                timeout_seconds=3600,
                skip_result=MonitorOutput(final_status="SUCCEEDED"),
            )

            # Persist log pointers before the failure check so a failed stage
            # still leaves its logs artifact open for debugging.
            if monitor_out.logs_uri:
                await self._persist_named_artifact(
                    input=input,
                    stage=stage,
                    step_name="monitor_training",
                    artifact_label="logs",
                    payload={
                        "logs_uri": monitor_out.logs_uri,
                        "log_tail": monitor_out.log_tail or [],
                        "final_status": monitor_out.final_status,
                    },
                )

            if _is_failed_status(monitor_out.final_status):
                raise ApplicationError(
                    f"stage {stage.stage_id} failed for {submit_out.auto_job_name}: {monitor_out.final_status}"
                )

            checkpoint = f"{checkpoint}/{stage.stage_id}"

            if self._replay_target and self._replay_target.scope == "step" and self._replay_target.target_stage_id == stage.stage_id:
                self._replay_target = None

        self.state = "COMPLETED"
        return f"KILVIN_TRAINING_COMPLETED:{input.run_config.run_id}"
