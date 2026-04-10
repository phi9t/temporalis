from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Mapping, TypeVar, get_args, get_origin, get_type_hints

from temporalio.common import RetryPolicy as TemporalRetryPolicy


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _enum_type_for_annotation(annotation: Any) -> type[Enum] | None:
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation

    origin = get_origin(annotation)
    if origin is None:
        return None

    for arg in get_args(annotation):
        if arg is type(None):
            continue
        enum_type = _enum_type_for_annotation(arg)
        if enum_type is not None:
            return enum_type

    return None


StateT = TypeVar("StateT", bound="PipelineState")


@dataclass
class PipelineState:
    run_id: str
    status: str = "pending"
    failure_step: str | None = None
    failure_reason: str | None = None
    started_at: str | None = None
    updated_at: str | None = None

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {}

    def to_dict(self) -> dict[str, Any]:
        return {field.name: _serialize(getattr(self, field.name)) for field in fields(self)}

    @classmethod
    def from_dict(cls: type[StateT], data: Mapping[str, Any]) -> StateT:
        enum_fields = dict(getattr(cls, "_enum_fields", {}))
        type_hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for field in fields(cls):
            if field.name not in data:
                continue

            value = data[field.name]
            enum_type = enum_fields.get(field.name) or _enum_type_for_annotation(
                type_hints.get(field.name, field.type)
            )
            if enum_type is not None and value is not None and not isinstance(value, enum_type):
                kwargs[field.name] = enum_type(value)
            else:
                kwargs[field.name] = value
        return cls(**kwargs)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff: float = 1.0
    max_interval_seconds: int = 300

    def to_temporal_retry_policy(self) -> TemporalRetryPolicy:
        return TemporalRetryPolicy(
            maximum_attempts=self.max_attempts,
            backoff_coefficient=self.backoff,
            maximum_interval=timedelta(seconds=self.max_interval_seconds),
        )


@dataclass(frozen=True)
class RuntimeConfig:
    namespace: str = "default"
    task_queue_prefix: str = "inspectl"
    local_state_dir: Path = Path(".inspectl")
    log_dir: Path = Path("runs")
    temporal_cli_path: str = "temporal"
    host: str = "127.0.0.1"
    port: int = 7233
