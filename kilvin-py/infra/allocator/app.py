"""FastAPI resource allocator: a finite CPU/memory ledger over HTTP."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ledger import CapacityError, ClusterInventory, Ledger


class AllocationRequest(BaseModel):
    run_id: str
    stage_id: str
    cpus: int
    memory_gb: int


def load_inventory(path: Path) -> ClusterInventory:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ClusterInventory(
        name=raw["name"],
        cpus=int(raw["cpus"]),
        memory_gb=int(raw["memory_gb"]),
    )


def create_app(inventory: ClusterInventory) -> FastAPI:
    app = FastAPI(title="kilvin-resource-allocator")
    ledger = Ledger(inventory)

    @app.get("/healthz")
    def healthz() -> dict:
        free_cpus, free_mem = ledger.available()
        return {
            "status": "ok",
            "cluster": inventory.name,
            "free_cpus": free_cpus,
            "free_memory_gb": free_mem,
        }

    @app.post("/v1/allocations")
    def allocate(request: AllocationRequest) -> dict:
        try:
            allocation = ledger.allocate(
                run_id=request.run_id,
                stage_id=request.stage_id,
                cpus=request.cpus,
                memory_gb=request.memory_gb,
            )
        except CapacityError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        return asdict(allocation)

    @app.delete("/v1/allocations/{allocation_id}")
    def release(allocation_id: str) -> dict:
        if not ledger.release(allocation_id):
            raise HTTPException(status_code=404, detail=f"unknown allocation {allocation_id}")
        return {"released": allocation_id}

    @app.get("/v1/allocations")
    def live() -> dict:
        return {"allocations": [asdict(a) for a in ledger.live()]}

    return app


inventory_path = Path(os.environ.get("INVENTORY_PATH", Path(__file__).parent / "inventory.yaml"))
app = create_app(load_inventory(inventory_path))
