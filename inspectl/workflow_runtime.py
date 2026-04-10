from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, get_type_hints

from temporalio import workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from inspectl.activity_runtime import PAUSABLE_STEP_FAILURE_TYPE
    from inspectl.decorators import reset_dispatcher, set_dispatcher
    from inspectl.models import PipelineState
    from inspectl.registry import StepDefinition, get_pipeline


@dataclass
class DispatchState:
    state: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    failure_step: str | None = None
    failure_reason: str | None = None
    resume_requested: bool = False


class WorkflowStepDispatcher:
    def __init__(self, runtime: "InspectlPipelineWorkflow", log_dir: str) -> None:
        self.runtime = runtime
        self.log_dir = log_dir

    async def call_step(
        self, definition: StepDefinition, state: PipelineState, *args: Any, **kwargs: Any
    ) -> PipelineState:
        while True:
            try:
                payload = {
                    "state": state.to_dict(),
                    "log_dir": self.log_dir,
                    "args": list(args),
                    "kwargs": kwargs,
                }
                result = await workflow.execute_activity(
                    definition.name,
                    payload,
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=definition.retry_policy.to_temporal_retry_policy(),
                )
                restored = type(state).from_dict(result)
                self.runtime._dispatch.state = restored.to_dict()
                self.runtime._dispatch.status = "running"
                self.runtime._dispatch.failure_step = None
                self.runtime._dispatch.failure_reason = None
                return restored
            except Exception as exc:
                if not _is_pausable_step_failure(exc):
                    raise
                self.runtime._dispatch.status = "paused"
                self.runtime._dispatch.failure_step = definition.name
                self.runtime._dispatch.failure_reason = _pausable_failure_reason(exc)
                await workflow.wait_condition(lambda: self.runtime._dispatch.resume_requested)
                self.runtime._dispatch.resume_requested = False
                self.runtime._dispatch.status = "running"


def _pipeline_state_type(pipeline) -> type[PipelineState]:
    state_type = get_type_hints(pipeline.fn).get("state")
    if not isinstance(state_type, type) or not issubclass(state_type, PipelineState):
        raise TypeError(f"pipeline '{pipeline.name}' is missing a valid state annotation")
    return state_type


def _application_error_in_chain(exc: BaseException) -> ApplicationError | None:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ApplicationError):
            return current
        current = getattr(current, "cause", None)
    return None


def _is_pausable_step_failure(exc: BaseException) -> bool:
    app_error = _application_error_in_chain(exc)
    return app_error is not None and app_error.type == PAUSABLE_STEP_FAILURE_TYPE


def _pausable_failure_reason(exc: BaseException) -> str:
    app_error = _application_error_in_chain(exc)
    if app_error is not None:
        return app_error.message
    return str(exc)


@workflow.defn(sandboxed=False)
class InspectlPipelineWorkflow:
    def __init__(self) -> None:
        self._dispatch = DispatchState()

    @workflow.signal
    def resume(self) -> None:
        self._dispatch.resume_requested = True

    @workflow.query
    def describe(self) -> dict[str, Any]:
        return {
            "status": self._dispatch.status,
            "failure_step": self._dispatch.failure_step,
            "failure_reason": self._dispatch.failure_reason,
            "state": self._dispatch.state,
        }

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        pipeline = get_pipeline(payload["pipeline_name"])
        state_type = _pipeline_state_type(pipeline)
        state = state_type.from_dict(payload["state"])
        self._dispatch.state = state.to_dict()
        self._dispatch.status = "running"

        dispatcher = WorkflowStepDispatcher(self, payload["log_dir"])
        token = set_dispatcher(dispatcher)
        try:
            result = await pipeline.fn(state)
            self._dispatch.state = result.to_dict()
            self._dispatch.status = "completed"
            return result.to_dict()
        finally:
            reset_dispatcher(token)
