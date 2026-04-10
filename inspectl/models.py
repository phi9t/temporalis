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


def _is_dataclass_type(annotation: Any) -> bool:
    return isinstance(annotation, type) and is_dataclass(annotation)


def _is_special_union_candidate(annotation: Any) -> bool:
    return (
        _enum_type_for_annotation(annotation) is not None
        or annotation is Path
        or _is_dataclass_type(annotation)
        or get_origin(annotation) in {list, tuple, set, frozenset, dict}
    )


def _deserialize(value: Any, annotation: Any, *, field_name: str | None = None) -> Any:
    if value is None:
        return None

    origin = get_origin(annotation)
    enum_type = _enum_type_for_annotation(annotation)
    if origin is None and enum_type is not None:
        if isinstance(value, enum_type):
            return value
        return enum_type(value)

    if annotation is Path:
        if isinstance(value, Path):
            return value
        return Path(value)

    if origin is list:
        item_annotation = get_args(annotation)[0] if get_args(annotation) else Any
        return [_deserialize(item, item_annotation, field_name=field_name) for item in value]
    if origin is tuple:
        item_annotations = get_args(annotation)
        if len(item_annotations) == 2 and item_annotations[1] is Ellipsis:
            return tuple(
                _deserialize(item, item_annotations[0], field_name=field_name) for item in value
            )
        if item_annotations:
            if len(value) != len(item_annotations):
                label = f" '{field_name}'" if field_name is not None else ""
                raise ValueError(
                    f"tuple field{label} expected {len(item_annotations)} items but got {len(value)}"
                )
            return tuple(
                _deserialize(item, item_annotations[index], field_name=field_name)
                for index, item in enumerate(value)
            )
        return tuple(value)
    if origin is set:
        item_annotation = get_args(annotation)[0] if get_args(annotation) else Any
        return {_deserialize(item, item_annotation, field_name=field_name) for item in value}
    if origin is frozenset:
        item_annotation = get_args(annotation)[0] if get_args(annotation) else Any
        return frozenset(_deserialize(item, item_annotation, field_name=field_name) for item in value)
    if origin is dict:
        key_annotation, value_annotation = (get_args(annotation) + (Any, Any))[:2]
        return {
            _deserialize(key, key_annotation, field_name=field_name): _deserialize(
                item, value_annotation, field_name=field_name
            )
            for key, item in value.items()
        }
    if origin is not None:
        candidates = [arg for arg in get_args(annotation) if arg is not type(None)]
        special_candidates = [candidate for candidate in candidates if _is_special_union_candidate(candidate)]
        primitive_candidates = [candidate for candidate in candidates if candidate not in special_candidates]

        for candidate in special_candidates:
            candidate_enum_type = _enum_type_for_annotation(candidate)
            if candidate_enum_type is not None:
                try:
                    converted = _deserialize(value, candidate, field_name=field_name)
                except (TypeError, ValueError):
                    continue
            else:
                converted = _deserialize(value, candidate, field_name=field_name)
            if converted is not value:
                return converted
            if isinstance(candidate, type) and isinstance(value, candidate):
                return converted

        for candidate in primitive_candidates:
            if isinstance(candidate, type) and isinstance(value, candidate):
                return value
        return value

    if _is_dataclass_type(annotation):
        if isinstance(value, annotation):
            return value
        if not isinstance(value, Mapping):
            return value
        type_hints = get_type_hints(annotation)
        kwargs: dict[str, Any] = {}
        for field in fields(annotation):
            if field.name not in value:
                continue
            kwargs[field.name] = _deserialize(
                value[field.name],
                type_hints.get(field.name, field.type),
                field_name=field.name,
            )
        return annotation(**kwargs)

    return value


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
        type_hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for field in fields(cls):
            if field.name not in data:
                continue

            kwargs[field.name] = _deserialize(
                data[field.name],
                type_hints.get(field.name, field.type),
                field_name=field.name,
            )
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
