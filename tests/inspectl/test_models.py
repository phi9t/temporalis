from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest
from temporalio.common import RetryPolicy as TemporalRetryPolicy

from inspectl.models import PipelineState, RetryPolicy


class PipelineMode(str, Enum):
    COMMIT_FIRST = "commit-first"


class DeliveryMode(str, Enum):
    FAST = "fast"


@dataclass
class NestedSettings:
    root: Path
    label: str


@dataclass
class PathLikeState(PipelineState):
    resource: str | Path | None = None


@dataclass
class EnumFallbackState(PipelineState):
    mode: DeliveryMode | str | None = None


@dataclass
class TupleState(PipelineState):
    pair: tuple[str, Path] | None = None


@dataclass
class ExampleState(PipelineState):
    pipeline_mode: PipelineMode | None = None
    build_id: str | None = None
    workspace_dir: Path | None = None
    nested: NestedSettings | None = None


def test_pipeline_state_to_dict_serializes_enums() -> None:
    state = ExampleState(
        run_id="run-001",
        status="running",
        pipeline_mode=PipelineMode.COMMIT_FIRST,
        build_id="build-123",
    )

    payload = state.to_dict()

    assert payload["run_id"] == "run-001"
    assert payload["pipeline_mode"] == "commit-first"
    assert payload["build_id"] == "build-123"


def test_pipeline_state_from_dict_round_trips() -> None:
    restored = ExampleState.from_dict(
        {
            "run_id": "run-002",
            "status": "paused",
            "failure_step": "submit_compilation",
            "pipeline_mode": "commit-first",
            "build_id": "build-456",
            "workspace_dir": "/tmp/workspace",
            "nested": {"root": "/tmp/workspace/nested", "label": "nested"},
        }
    )

    assert restored.run_id == "run-002"
    assert restored.status == "paused"
    assert restored.failure_step == "submit_compilation"
    assert restored.pipeline_mode is PipelineMode.COMMIT_FIRST
    assert restored.build_id == "build-456"


def test_pipeline_state_round_trips_path_and_nested_dataclass_fields() -> None:
    state = ExampleState(
        run_id="run-003",
        status="running",
        pipeline_mode=PipelineMode.COMMIT_FIRST,
        build_id="build-789",
        workspace_dir=Path("/tmp/workspace"),
        nested=NestedSettings(root=Path("/tmp/workspace/nested"), label="nested"),
    )

    restored = ExampleState.from_dict(state.to_dict())

    assert isinstance(restored.workspace_dir, Path)
    assert restored.workspace_dir == Path("/tmp/workspace")
    assert isinstance(restored.nested, NestedSettings)
    assert restored.nested == NestedSettings(
        root=Path("/tmp/workspace/nested"),
        label="nested",
    )


def test_pipeline_state_prefers_path_over_string_in_unions() -> None:
    state = PathLikeState(run_id="run-004", resource=Path("/tmp/resource"))

    restored = PathLikeState.from_dict(state.to_dict())

    assert isinstance(restored.resource, Path)
    assert restored.resource == Path("/tmp/resource")


def test_pipeline_state_allows_enum_fallback_to_string() -> None:
    restored = EnumFallbackState.from_dict(
        {
            "run_id": "run-006",
            "mode": "manual",
        }
    )

    assert restored.mode == "manual"


def test_pipeline_state_rejects_extra_fixed_tuple_elements() -> None:
    with pytest.raises(ValueError, match="tuple field 'pair'"):
        TupleState.from_dict(
            {
                "run_id": "run-005",
                "pair": ["left", "/tmp/right", "unexpected"],
            }
        )


def test_retry_policy_maps_to_temporal_policy() -> None:
    policy = RetryPolicy(max_attempts=3, backoff=2.0, max_interval_seconds=45)

    temporal_policy = policy.to_temporal_retry_policy()

    assert isinstance(temporal_policy, TemporalRetryPolicy)
    assert temporal_policy.maximum_attempts == 3
    assert temporal_policy.backoff_coefficient == 2.0
    assert temporal_policy.maximum_interval.total_seconds() == 45
