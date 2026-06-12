"""Environment-driven settings for the host worker and starter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

KILVIN_PY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class KilvinSettings:
    temporal_address: str
    allocator_url: str
    registry: str
    namespace: str
    trainer_dir: Path
    kubeconfig_path: Path

    @classmethod
    def load(cls) -> "KilvinSettings":
        return cls(
            temporal_address=os.environ.get("KILVIN_TEMPORAL_ADDRESS", "localhost:7233"),
            allocator_url=os.environ.get("KILVIN_ALLOCATOR_URL", "http://localhost:7070"),
            registry=os.environ.get("KILVIN_REGISTRY", "localhost:5001"),
            namespace=os.environ.get("KILVIN_K8S_NAMESPACE", "kilvin-training"),
            trainer_dir=Path(os.environ.get("KILVIN_TRAINER_DIR", KILVIN_PY_ROOT / "trainer")),
            kubeconfig_path=Path(
                os.environ.get(
                    "KILVIN_KUBECONFIG",
                    KILVIN_PY_ROOT / "infra" / ".kubeconfig" / "kubeconfig.yaml",
                )
            ),
        )
