"""Finite CPU/memory ledger for one local cluster. In-memory; reset on restart."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


class CapacityError(Exception):
    """Raised when the requested resources exceed what remains in the pool."""


@dataclass(frozen=True)
class ClusterInventory:
    name: str
    cpus: int
    memory_gb: int


@dataclass(frozen=True)
class Allocation:
    allocation_id: str
    run_id: str
    stage_id: str
    cluster: str
    cpus_granted: int
    memory_gb_granted: int
    quota_decision: dict


@dataclass
class Ledger:
    inventory: ClusterInventory
    _live: dict[str, Allocation] = field(default_factory=dict)

    def available(self) -> tuple[int, int]:
        used_cpus = sum(a.cpus_granted for a in self._live.values())
        used_mem = sum(a.memory_gb_granted for a in self._live.values())
        return self.inventory.cpus - used_cpus, self.inventory.memory_gb - used_mem

    def allocate(
        self,
        *,
        run_id: str,
        stage_id: str,
        cpus: int,
        memory_gb: int,
    ) -> Allocation:
        free_cpus, free_mem = self.available()
        if cpus > free_cpus:
            raise CapacityError(
                f"quota exhausted on {self.inventory.name}: requested {cpus} cpus, {free_cpus} free"
            )
        if memory_gb > free_mem:
            raise CapacityError(
                f"quota exhausted on {self.inventory.name}: requested {memory_gb}GB, {free_mem}GB free"
            )
        allocation = Allocation(
            allocation_id=f"alloc-{uuid.uuid4().hex[:10]}",
            run_id=run_id,
            stage_id=stage_id,
            cluster=self.inventory.name,
            cpus_granted=cpus,
            memory_gb_granted=memory_gb,
            quota_decision={
                "cluster": self.inventory.name,
                "cpus_requested": cpus,
                "cpus_granted": cpus,
                "memory_gb_requested": memory_gb,
                "memory_gb_granted": memory_gb,
                "cpus_available_before": free_cpus,
                "memory_gb_available_before": free_mem,
                "reason": (
                    f"{cpus} cpus / {memory_gb}GB fit on {self.inventory.name} "
                    f"({free_cpus} cpus, {free_mem}GB free at decision time)"
                ),
            },
        )
        self._live[allocation.allocation_id] = allocation
        return allocation

    def release(self, allocation_id: str) -> bool:
        return self._live.pop(allocation_id, None) is not None

    def live(self) -> list[Allocation]:
        return list(self._live.values())
