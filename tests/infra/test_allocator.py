from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kilvin-py" / "infra" / "allocator"))

from ledger import CapacityError, ClusterInventory, Ledger  # noqa: E402


def make_ledger() -> Ledger:
    return Ledger(ClusterInventory(name="local-k3s", cpus=4, memory_gb=8))


def test_ledger_grants_and_tracks_capacity() -> None:
    ledger = make_ledger()
    grant = ledger.allocate(run_id="run-a", stage_id="pretrain", cpus=2, memory_gb=4)

    assert grant.cluster == "local-k3s"
    assert grant.cpus_granted == 2
    assert grant.allocation_id
    assert grant.quota_decision["cpus_available_before"] == 4
    assert ledger.available() == (2, 4)


def test_ledger_rejects_when_exhausted_and_releases() -> None:
    ledger = make_ledger()
    grant = ledger.allocate(run_id="run-a", stage_id="pretrain", cpus=4, memory_gb=4)

    with pytest.raises(CapacityError, match="cpus"):
        ledger.allocate(run_id="run-b", stage_id="pretrain", cpus=1, memory_gb=1)

    assert ledger.release(grant.allocation_id) is True
    assert ledger.release(grant.allocation_id) is False
    assert ledger.available() == (4, 8)


def test_app_grant_exhaust_409_release_cycle() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app import create_app

    app = create_app(ClusterInventory(name="local-k3s", cpus=2, memory_gb=4))
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200

    granted = client.post(
        "/v1/allocations",
        json={"run_id": "run-a", "stage_id": "pretrain", "cpus": 2, "memory_gb": 4},
    )
    assert granted.status_code == 200
    body = granted.json()
    assert body["cluster"] == "local-k3s"
    assert body["quota_decision"]["reason"]

    rejected = client.post(
        "/v1/allocations",
        json={"run_id": "run-b", "stage_id": "pretrain", "cpus": 1, "memory_gb": 1},
    )
    assert rejected.status_code == 409
    assert "exhausted" in rejected.json()["detail"]

    listing = client.get("/v1/allocations").json()
    assert len(listing["allocations"]) == 1

    released = client.delete(f"/v1/allocations/{body['allocation_id']}")
    assert released.status_code == 200
    assert client.get("/v1/allocations").json()["allocations"] == []
