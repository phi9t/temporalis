from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Any

import temporalio.common
import temporalio.exceptions
import temporalio.workflow

with temporalio.workflow.unsafe.imports_passed_through():
    from . import activities

from .models import (
    AllocateResourcesInput,
    ArtifactWriteInput,
    CancelSignal,
    ConcretizeDependenciesInput,
    ConcretizeDependenciesOutput,
    InterpretIntentInput,
    KilvinRunState,
    MaterializedBundleOutput,
    MaterializeTrainingBundleInput,
    MonitorOutput,
    MonitorTrainingInput,
    PauseAtStepSignal,
    PauseSignal,
    ReplaySignal,
    ResourceAllocationOutput,
    ResumeSignal,
    RunConfig,
    StageConfig,
    StageExecutionFailure,
    StepExecutionEnvelope,
    SubmitK8sInput,
    SubmitK8sOutput,
    TrainingIntent,
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


@temporalio.workflow.defn
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

    @temporalio.workflow.query
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

    @temporalio.workflow.query
    def run_step_trace(self) -> list[StepExecutionEnvelope]:
        return list(self._step_traces)

    @temporalio.workflow.query
    def run_artifacts(self) -> list[str]:
        uris: list[str] = []
        for entry in self._step_traces:
            uris.append(entry.input_artifact.uri)
            if entry.output_artifact:
                uris.append(entry.output_artifact.uri)
        uris.extend(self._named_artifact_uris)
        return uris

    @temporalio.workflow.query
    def run_plan(self) -> list[str]:
        if self._run_config is None:
            return []
        return [stage.stage_id for stage in _ordered_stages(self._run_config)]

    @temporalio.workflow.signal
    def pause(self, _input: PauseSignal | None = None) -> None:
        self._paused = True
        self.state = "PAUSED"

    @temporalio.workflow.signal
    def resume(self, _input: ResumeSignal | None = None) -> None:
        self._paused = False
        if self.state == "PAUSED":
            self.state = "RUNNING"

    @temporalio.workflow.signal
    def pause_at_step(self, signal: PauseAtStepSignal) -> None:
        self._pause_filter = signal

    @temporalio.workflow.signal
    def replay_step(self, signal: ReplaySignal) -> None:
        self._run_attempt += 1
        self._replay_target = signal
        self._replay_step_waiting = signal.scope == "step"
        self._paused = False
        self.state = "RUNNING"

    @temporalio.workflow.signal
    def cancel(self, _input: CancelSignal | None = None) -> None:
        self._cancelled = True
        self._paused = False
        self._pause_filter = None
        self.state = "CANCELLED"

    def _matches_pause_at_step_filter(
        self, stage: StageConfig, step_name: str, when: str
    ) -> bool:
        if self._pause_filter is None:
            return False
        return (
            self._pause_filter.when == when
            and self._pause_filter.stage_id == stage.stage_id
            and self._pause_filter.step_name == step_name
        )

    async def _await_resume_from_pause(self) -> None:
        if not self._paused:
            return
        self.state = "PAUSED"
        await temporalio.workflow.wait_condition(lambda: not self._paused)
        if self._cancelled:
            raise temporalio.exceptions.ApplicationError(
                "training workflow cancelled", non_retryable=True
            )
        self.state = "RUNNING"

    def _find_replay_target_stage_index(self, stages: list[StageConfig]) -> int | None:
        if not self._replay_target:
            return None
        for idx, stage in enumerate(stages):
            if stage.stage_id == self._replay_target.target_stage_id:
                return idx
        return None

    def _should_skip_step_during_replay(
        self,
        stages: list[StageConfig],
        stage_index: int,
        step_name: str,
    ) -> bool:
        if not self._replay_target:
            return False
        target = self._replay_target
        target_stage_index = self._find_replay_target_stage_index(stages)
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

    def _record_step_trace_entry(
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

    async def _persist_step_input_artifact(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        step_name: str,
        payload: Any,
    ) -> StepExecutionEnvelope:
        artifact = await temporalio.workflow.execute_activity(
            activities.persist_yaml_artifact,
            ArtifactWriteInput(
                run_id=input.run_config.run_id,
                run_attempt=self._run_attempt,
                artifact_name=f"{stage.stage_id}/{step_name}/in.yaml",
                payload=_to_dict(payload),
            ),
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=temporalio.common.RetryPolicy(maximum_attempts=3),
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
            started_at_ms=int(temporalio.workflow.now().timestamp() * 1000),
        )

    async def _persist_supplementary_step_artifact(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        step_name: str,
        artifact_label: str,
        payload: Any,
    ) -> None:
        """Persist a hood-open artifact (quota decision, env vars, logs) beside the step record."""

        artifact = await temporalio.workflow.execute_activity(
            activities.persist_yaml_artifact,
            ArtifactWriteInput(
                run_id=input.run_config.run_id,
                run_attempt=self._run_attempt,
                artifact_name=f"{stage.stage_id}/{step_name}/{artifact_label}.yaml",
                payload=_to_dict(payload),
            ),
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=temporalio.common.RetryPolicy(maximum_attempts=3),
        )
        self._named_artifact_uris.append(artifact.uri)

    async def _record_replay_skipped_step(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        step_name: str,
        payload: Any,
        reason: str,
    ) -> None:
        envelope = await self._persist_step_input_artifact(
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
        self._record_step_trace_entry(
            run_id=input.run_config.run_id,
            stage=stage,
            stage_index=stage_index,
            step_name=step_name,
            status="SKIPPED",
            input_artifact=envelope.input_artifact,
            input_checksum=envelope.input_checksum,
            error=reason,
            started_at_ms=envelope.started_at_ms,
            completed_at_ms=int(temporalio.workflow.now().timestamp() * 1000),
        )

    async def _execute_tracked_training_step(
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
            raise temporalio.exceptions.ApplicationError(
                "training workflow cancelled", non_retryable=True
            )

        if self._matches_pause_at_step_filter(stage, step_name, "pre"):
            self._paused = True
            self._pause_filter = None

        await self._await_resume_from_pause()

        stages = _ordered_stages(input.run_config)
        if self._should_skip_step_during_replay(
            stages=stages,
            stage_index=stage_index,
            step_name=step_name,
        ):
            await self._record_replay_skipped_step(
                input=input,
                stage=stage,
                stage_index=stage_index,
                step_name=step_name,
                payload=activity_input,
                reason=(
                    "skipped for replay scope="
                    f"{self._replay_target.scope if self._replay_target else 'none'}"
                ),
            )
            return skip_result

        envelope = await self._persist_step_input_artifact(input, stage, stage_index, step_name, {
            "step_name": step_name,
            "stage_id": stage.stage_id,
            "run_id": input.run_config.run_id,
            "run_attempt": self._run_attempt,
            "payload": _to_dict(activity_input),
        })
        self._current_step = (stage.stage_id, step_name)
        self._record_step_trace_entry(
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
            output = await temporalio.workflow.execute_activity(
                activity_fn,
                activity_input,
                start_to_close_timeout=timedelta(seconds=timeout_seconds),
                retry_policy=temporalio.common.RetryPolicy(
                    maximum_attempts=retry_attempts or 3,
                    initial_interval=timedelta(seconds=5),
                ),
            )

            output_artifact = await temporalio.workflow.execute_activity(
                activities.persist_yaml_artifact,
                ArtifactWriteInput(
                    run_id=input.run_config.run_id,
                    run_attempt=self._run_attempt,
                    artifact_name=f"{stage.stage_id}/{step_name}/out.yaml",
                    payload=_to_dict(output),
                ),
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=temporalio.common.RetryPolicy(maximum_attempts=3),
            )
            self._record_step_trace_entry(
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
                completed_at_ms=int(temporalio.workflow.now().timestamp() * 1000),
            )
            if self._matches_pause_at_step_filter(stage, step_name, "post"):
                self._paused = True
                self._pause_filter = None
            await self._await_resume_from_pause()
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
            self._record_step_trace_entry(
                run_id=input.run_config.run_id,
                stage=stage,
                stage_index=stage_index,
                step_name=step_name,
                status="FAILED",
                input_artifact=envelope.input_artifact,
                input_checksum=envelope.input_checksum,
                error=str(err),
                started_at_ms=envelope.started_at_ms,
                completed_at_ms=int(temporalio.workflow.now().timestamp() * 1000),
            )
            raise

    def _prepare_training_run(self, input: TrainingWorkflowInput) -> list[StageConfig]:
        self._run_id = input.run_config.run_id
        self._run_config = input.run_config
        self._run_attempt += 1

        try:
            _validate_run_config(input.run_config)
        except ValueError as err:
            raise temporalio.exceptions.ApplicationError(str(err), non_retryable=True) from err

        stages = _ordered_stages(input.run_config)
        if not stages:
            raise temporalio.exceptions.ApplicationError(
                f"No enabled stages configured for {self._run_id}", non_retryable=True
            )
        return stages

    async def _interpret_training_intent(
        self,
        input: TrainingWorkflowInput,
        stages: list[StageConfig],
    ) -> TrainingIntent:
        return await self._execute_tracked_training_step(
            input=input,
            stage=stages[0],
            stage_index=0,
            step_name="interpret_intent",
            activity_fn=activities.interpret_training_intent,
            activity_input=InterpretIntentInput(
                run_config=input.run_config,
                job_params_uri=input.job_params_uri,
            ),
            timeout_seconds=30,
            skip_result=TrainingIntent(
                model_output_tos_key=input.job_params_uri,
                workflow_config_uri=(
                    f"file://./.kilvin-cache/{input.run_config.run_id}/workflow.yaml"
                ),
                checkpoint="s3://checkpoints/model-x/base",
                stage_index=0,
                component_profile={
                    "run_name": input.run_config.kilvin_run_name,
                    "model": "model-x",
                    "dataset_root": stages[0].dataset_profile.uri,
                    "spec_version": input.run_config.workflow_spec,
                },
                image_ref=f"localhost:5001/kilvin-trainer:{input.run_config.run_id}",
                trainer_env={},
            ),
        )

    async def _concretize_training_dependencies(
        self,
        input: TrainingWorkflowInput,
        stages: list[StageConfig],
        training_intent: TrainingIntent,
    ) -> ConcretizeDependenciesOutput:
        return await self._execute_tracked_training_step(
            input=input,
            stage=stages[0],
            stage_index=0,
            step_name="concretize_dependencies",
            activity_fn=activities.concretize_dependencies,
            activity_input=ConcretizeDependenciesInput(
                run_id=input.run_config.run_id,
                checkpoint=training_intent.checkpoint,
                image_ref=training_intent.image_ref,
            ),
            timeout_seconds=900,
            skip_result=ConcretizeDependenciesOutput(
                image_ref=training_intent.image_ref,
                image_digest="sha256:replayed",
                lockfile_sha256="replayed",
            ),
        )

    def _build_image_digest_ref(
        self, dependency_resolution: ConcretizeDependenciesOutput
    ) -> str:
        if dependency_resolution.image_digest.startswith("sha256:"):
            return f"{dependency_resolution.image_ref}@{dependency_resolution.image_digest}"
        return dependency_resolution.image_ref

    async def _execute_training_stage(
        self,
        input: TrainingWorkflowInput,
        stage: StageConfig,
        stage_index: int,
        training_intent: TrainingIntent,
        digest_ref: str,
        ir_name: str,
        checkpoint: str,
    ) -> str:
        resource_allocation = await self._execute_tracked_training_step(
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
                cpus=training_intent.cpus,
                memory_gb=training_intent.memory_gb,
            ),
            timeout_seconds=180,
            retry_attempts=6,
            skip_result=ResourceAllocationOutput(
                allocation_id=f"skip-allocation-{stage.stage_id}",
                cluster="local-k3s",
                cpus=1,
                memory_gb=1,
            ),
        )

        if resource_allocation.quota_decision is not None:
            await self._persist_supplementary_step_artifact(
                input=input,
                stage=stage,
                step_name="allocate_resources",
                artifact_label="quota_decision",
                payload=resource_allocation.quota_decision,
            )

        training_bundle = await self._execute_tracked_training_step(
            input=input,
            stage=stage,
            stage_index=stage_index,
            step_name="materialize_training_bundle",
            activity_fn=activities.materialize_training_bundle,
            activity_input=MaterializeTrainingBundleInput(
                ir_name=f"{ir_name}-{stage.stage_id}",
                checkpoint=checkpoint,
                config_snapshot=training_intent.workflow_config_uri,
                allocation=resource_allocation,
                stage_index=stage_index,
                train_stage=stage.stage_id,
                task_type="train",
                image_ref=digest_ref,
                trainer_env=dict(training_intent.trainer_env or {}),
                model=training_intent.component_profile.get("model", "model-x"),
                run_id=input.run_config.run_id,
            ),
            timeout_seconds=60,
            skip_result=MaterializedBundleOutput(
                bundle_id=f"skip-bundle-{stage.stage_id}",
                bundle_path="skipped://bundle",
                job_manifest={},
                env_vars={},
                launch_plan=[],
                health_checks=[],
            ),
        )

        if training_bundle.env_vars:
            await self._persist_supplementary_step_artifact(
                input=input,
                stage=stage,
                step_name="materialize_training_bundle",
                artifact_label="env_vars",
                payload=training_bundle.env_vars,
            )

        k8s_submission = await self._execute_tracked_training_step(
            input=input,
            stage=stage,
            stage_index=stage_index,
            step_name="submit_k8s_job",
            activity_fn=activities.submit_k8s_job,
            activity_input=SubmitK8sInput(
                stage_id=stage.stage_id,
                bundle=training_bundle,
                namespace="kilvin-training",
            ),
            timeout_seconds=120,
            skip_result=SubmitK8sOutput(
                job_name=f"replay-skip-{stage.stage_id}",
                job_uid="skip-replay",
                k8s_namespace="kilvin-training",
            ),
        )

        training_monitor_result = await self._execute_tracked_training_step(
            input=input,
            stage=stage,
            stage_index=stage_index,
            step_name="monitor_training",
            activity_fn=activities.monitor_training,
            activity_input=MonitorTrainingInput(
                job_name=k8s_submission.job_name,
                job_uid=k8s_submission.job_uid,
                ir_name=f"{ir_name}-{stage.stage_id}",
                k8s_namespace=k8s_submission.k8s_namespace,
                allocation_id=resource_allocation.allocation_id,
            ),
            timeout_seconds=3600,
            skip_result=MonitorOutput(final_status="SUCCEEDED"),
        )

        # Persist log pointers before the failure check so a failed stage
        # still leaves its logs artifact open for debugging.
        if training_monitor_result.logs_uri:
            await self._persist_supplementary_step_artifact(
                input=input,
                stage=stage,
                step_name="monitor_training",
                artifact_label="logs",
                payload={
                    "logs_uri": training_monitor_result.logs_uri,
                    "log_tail": training_monitor_result.log_tail or [],
                    "final_status": training_monitor_result.final_status,
                },
            )

        if _is_failed_status(training_monitor_result.final_status):
            raise temporalio.exceptions.ApplicationError(
                f"stage {stage.stage_id} failed for {k8s_submission.job_name}: "
                f"{training_monitor_result.final_status}"
            )

        if (
            self._replay_target
            and self._replay_target.scope == "step"
            and self._replay_target.target_stage_id == stage.stage_id
        ):
            self._replay_target = None

        return f"{checkpoint}/{stage.stage_id}"

    @temporalio.workflow.run
    async def run(self, input: TrainingWorkflowInput) -> str:
        stages = self._prepare_training_run(input)

        training_intent = await self._interpret_training_intent(input, stages)
        dependency_resolution = await self._concretize_training_dependencies(
            input, stages, training_intent
        )

        checkpoint = training_intent.checkpoint or "scratch"
        digest_ref = self._build_image_digest_ref(dependency_resolution)
        ir_name = f"kilvin-ir-{input.run_config.run_id}"

        for stage_index, stage in enumerate(stages):
            if self._cancelled:
                break
            checkpoint = await self._execute_training_stage(
                input=input,
                stage=stage,
                stage_index=stage_index,
                training_intent=training_intent,
                digest_ref=digest_ref,
                ir_name=ir_name,
                checkpoint=checkpoint,
            )

        self.state = "COMPLETED"
        return f"KILVIN_TRAINING_COMPLETED:{input.run_config.run_id}"
