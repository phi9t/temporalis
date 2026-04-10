from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from temporalio.common import RetryPolicy as TemporalRetryPolicy

from inspectl.models import PipelineState, RetryPolicy


class PipelineMode(str, Enum):
    COMMIT_FIRST = "commit-first"


@dataclass
class ExampleState(PipelineState):
    pipeline_mode: PipelineMode | None = None
    build_id: str | None = None


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
        }
    )

    assert restored.run_id == "run-002"
    assert restored.status == "paused"
    assert restored.failure_step == "submit_compilation"
    assert restored.pipeline_mode is PipelineMode.COMMIT_FIRST
    assert restored.build_id == "build-456"


def test_retry_policy_maps_to_temporal_policy() -> None:
    policy = RetryPolicy(max_attempts=3, backoff=2.0, max_interval_seconds=45)

    temporal_policy = policy.to_temporal_retry_policy()

    assert isinstance(temporal_policy, TemporalRetryPolicy)
    assert temporal_policy.maximum_attempts == 3
    assert temporal_policy.backoff_coefficient == 2.0
    assert temporal_policy.maximum_interval.total_seconds() == 45
