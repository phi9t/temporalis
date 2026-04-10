from __future__ import annotations

from pathlib import Path

import yaml

from monoctl.models import Manifest, RepositorySpec


def load_manifest(path: Path) -> Manifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    repos = [RepositorySpec(**repo) for repo in raw.get("repos", [])]
    return Manifest(repos=repos)
