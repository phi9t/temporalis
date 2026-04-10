from __future__ import annotations

from collections.abc import Sequence
import inspect
from pathlib import Path
from typing import Any, get_type_hints

from temporalio import activity
from temporalio.common import RawValue
from temporalio.exceptions import ApplicationError

from inspectl.errors import StepExecutionError, StepPreconditionError
from inspectl.logging import RunSession, StepContext
from inspectl.models import PipelineState
from inspectl.registry import StepDefinition, get_step

PAUSABLE_STEP_FAILURE_TYPE = "inspectl.user_step_failure"


def _decode_input(args: Sequence[RawValue]) -> dict[str, Any]:
    if not args:
        raise StepExecutionError("step activity missing payload")
    return activity.payload_converter().from_payload(args[0].payload, dict)


def _state_type_for_step(definition: StepDefinition) -> type[PipelineState]:
    params = list(inspect.signature(definition.fn).parameters.values())
    if not params:
        raise StepExecutionError(f"step '{definition.name}' is missing a valid state annotation")

    state_param = params[0]
    state_type = get_type_hints(definition.fn).get(state_param.name, state_param.annotation)
    if not isinstance(state_type, type) or not issubclass(state_type, PipelineState):
        raise StepExecutionError(f"step '{definition.name}' is missing a valid state annotation")
    return state_type


def _restore_state(definition: StepDefinition, payload: dict[str, Any]) -> PipelineState:
    state_type = _state_type_for_step(definition)
    state_payload = payload.get("state")
    if not isinstance(state_payload, dict):
        raise StepExecutionError(f"step '{definition.name}' payload is missing serialized state")
    return state_type.from_dict(state_payload)


def _validate_requires(definition: StepDefinition, state: PipelineState) -> None:
    for field_name in definition.requires:
        if getattr(state, field_name, None) is None:
            raise StepPreconditionError(
                f"step '{definition.name}' requires '{field_name}' but it is None"
            )


def _wants_step_context(definition: StepDefinition) -> bool:
    params = list(inspect.signature(definition.fn).parameters.values())
    if len(params) < 2:
        return False

    context_param = params[1]
    context_type = get_type_hints(definition.fn).get(context_param.name, context_param.annotation)
    return isinstance(context_type, type) and issubclass(context_type, StepContext)


def _restore_call_arguments(payload: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    args = payload.get("args", [])
    kwargs = payload.get("kwargs", {})

    if not isinstance(args, list):
        raise StepExecutionError("step activity payload args must be a list")
    if not isinstance(kwargs, dict) or not all(isinstance(key, str) for key in kwargs):
        raise StepExecutionError("step activity payload kwargs must be a string-keyed dict")
    return args, kwargs


async def _invoke_step(
    definition: StepDefinition,
    state: PipelineState,
    ctx: StepContext,
    args: Sequence[Any],
    kwargs: dict[str, Any],
) -> PipelineState:
    try:
        if _wants_step_context(definition):
            result = definition.fn(state, ctx, *args, **kwargs)
        else:
            result = definition.fn(state, *args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        raise ApplicationError(
            str(exc),
            type=PAUSABLE_STEP_FAILURE_TYPE,
        ) from exc

    if result is None or not hasattr(result, "to_dict"):
        raise StepExecutionError(f"step '{definition.name}' returned invalid state")
    return result


@activity.defn(dynamic=True)
async def inspectl_step_activity(args: Sequence[RawValue]) -> dict[str, Any]:
    payload = _decode_input(args)
    definition = get_step(activity.info().activity_type)
    state = _restore_state(definition, payload)
    user_args, user_kwargs = _restore_call_arguments(payload)
    _validate_requires(definition, state)

    session = RunSession(run_id=state.run_id, root_dir=Path(payload["log_dir"]))
    session.record(
        level="INFO",
        event="step.start",
        message=f"starting {definition.name}",
        step=definition.name,
        attempt=activity.info().attempt,
    )
    ctx = StepContext(
        run_id=state.run_id,
        step_name=definition.name,
        attempt=activity.info().attempt,
        session=session,
    )

    try:
        result = await _invoke_step(definition, state, ctx, user_args, user_kwargs)
        session.record(
            level="INFO",
            event="step.success",
            message=f"completed {definition.name}",
            step=definition.name,
            attempt=activity.info().attempt,
        )
        session.snapshot(step_name=definition.name, state=result)
        return result.to_dict()
    finally:
        session.close()
