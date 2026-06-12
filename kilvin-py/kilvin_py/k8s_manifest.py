"""Render the Kubernetes Job manifest: the literal launch spec for one stage."""

from __future__ import annotations

from typing import Any


def render_job_manifest(
    *,
    job_name: str,
    namespace: str,
    image: str,
    env: dict[str, str],
    cpus: int,
    memory_gb: int,
    run_id: str,
    stage_id: str,
) -> dict[str, Any]:
    resources = {"cpu": str(cpus), "memory": f"{memory_gb}Gi"}
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": {
                "app": "kilvin-trainer",
                "kilvin.run-id": run_id,
                "kilvin.stage-id": stage_id,
            },
        },
        "spec": {
            # Temporal's retry policy owns re-attempts; the kubelet must not race it.
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "metadata": {"labels": {"app": "kilvin-trainer", "kilvin.run-id": run_id}},
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "trainer",
                            "image": image,
                            "env": [
                                {"name": key, "value": value}
                                for key, value in sorted(env.items())
                            ],
                            "resources": {"requests": dict(resources), "limits": dict(resources)},
                        }
                    ],
                },
            },
        },
    }
