from __future__ import annotations

import hashlib
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from .models import StepIOArtifact


def _to_local_path(uri: str) -> Path:
    if uri.startswith("file://"):
        return Path(uri.removeprefix("file://"))
    return Path(uri)


class ArtifactStore:
    """Filesystem-backed artifact ledger for step-level inspectability."""

    def __init__(self, root_uri: str = "file://./.kilvin-artifacts"):
        path = _to_local_path(root_uri)
        path.mkdir(parents=True, exist_ok=True)
        self.root = path

    def _artifact_path(self, run_id: str, run_attempt: int, name: str) -> Path:
        root = self.root / run_id / str(run_attempt) / "artifacts"
        root.mkdir(parents=True, exist_ok=True)
        return root / name

    def write_yaml(self, run_id: str, run_attempt: int, name: str, value: Any) -> StepIOArtifact:
        payload = yaml.safe_dump(asdict(value), sort_keys=True).encode("utf-8")
        checksum = hashlib.sha256(payload).hexdigest()
        dest = self._artifact_path(run_id, run_attempt, name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        return StepIOArtifact(
            uri=f"file://{dest.resolve()}",
            format="yaml",
            checksum_sha256=checksum,
            size_bytes=len(payload),
        )

    def read_yaml(self, artifact: StepIOArtifact) -> Any:
        return yaml.safe_load(Path(_to_local_path(artifact.uri)).read_text(encoding="utf-8"))

    def canonical_yaml_for_hash(self, value: Any) -> tuple[str, str]:
        payload = yaml.safe_dump(value, sort_keys=True).encode("utf-8")
        checksum = hashlib.sha256(payload).hexdigest()
        return payload.decode("utf-8"), checksum

    def uri_from_suffix(self, run_id: str, run_attempt: int, suffix: str) -> str:
        return f"file://{self._artifact_path(run_id, run_attempt, suffix).resolve()}"
