"""HTTP client for the resource-allocator service, with typed error mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

UP_HINT = "is the infra up? run kilvin-py/infra/up.sh"


class QuotaExhausted(Exception):
    """Pool has no capacity right now; retryable by Temporal policy."""


class AllocatorUnavailable(Exception):
    """The allocator service is unreachable; not retryable, infra is down."""


@dataclass(frozen=True)
class AllocationGrant:
    allocation_id: str
    cluster: str
    cpus_granted: int
    memory_gb_granted: int
    quota_decision: dict[str, Any]


class AllocatorClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, transport=self._transport, timeout=10.0)

    async def request_allocation(
        self,
        *,
        run_id: str,
        stage_id: str,
        cpus: int,
        memory_gb: int,
    ) -> AllocationGrant:
        try:
            async with self._client() as client:
                response = await client.post(
                    "/v1/allocations",
                    json={
                        "run_id": run_id,
                        "stage_id": stage_id,
                        "cpus": cpus,
                        "memory_gb": memory_gb,
                    },
                )
        except httpx.HTTPError as err:
            raise AllocatorUnavailable(
                f"allocator at {self._base_url} unreachable ({err}); {UP_HINT}"
            ) from err
        if response.status_code == 409:
            raise QuotaExhausted(response.json().get("detail", "quota exhausted"))
        response.raise_for_status()
        body = response.json()
        return AllocationGrant(
            allocation_id=body["allocation_id"],
            cluster=body["cluster"],
            cpus_granted=body["cpus_granted"],
            memory_gb_granted=body["memory_gb_granted"],
            quota_decision=body["quota_decision"],
        )

    async def release(self, allocation_id: str) -> None:
        try:
            async with self._client() as client:
                response = await client.delete(f"/v1/allocations/{allocation_id}")
        except httpx.HTTPError as err:
            raise AllocatorUnavailable(
                f"allocator at {self._base_url} unreachable ({err}); {UP_HINT}"
            ) from err
        if response.status_code not in (200, 404):
            response.raise_for_status()
