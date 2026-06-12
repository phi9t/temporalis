"""Thin wrapper over the kubernetes client for Job submit/status/logs.

Imports kubernetes lazily so test environments without the package can still
import kilvin_py.activities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class KubeconfigMissing(Exception):
    """Kubeconfig not found; infra is not up."""


class KubernetesJobs:
    def __init__(self, kubeconfig_path: Path) -> None:
        if not kubeconfig_path.exists():
            raise KubeconfigMissing(
                f"kubeconfig not found at {kubeconfig_path}; is the infra up? run kilvin-py/infra/up.sh"
            )
        self._kubeconfig = str(kubeconfig_path)

    def _clients(self):
        from kubernetes import client, config

        api_client = config.new_client_from_config(config_file=self._kubeconfig)
        return client.BatchV1Api(api_client), client.CoreV1Api(api_client)

    def create_job(self, manifest: dict[str, Any]) -> tuple[str, str]:
        batch, _ = self._clients()
        created = batch.create_namespaced_job(
            namespace=manifest["metadata"]["namespace"],
            body=manifest,
        )
        return created.metadata.name, created.metadata.uid

    def job_status(self, name: str, namespace: str) -> str:
        """Return RUNNING, SUCCEEDED, or FAILED based on Job conditions."""
        batch, _ = self._clients()
        status = batch.read_namespaced_job_status(name=name, namespace=namespace).status
        for condition in status.conditions or []:
            if condition.type == "Complete" and condition.status == "True":
                return "SUCCEEDED"
            if condition.type == "Failed" and condition.status == "True":
                return "FAILED"
        return "RUNNING"

    def pod_log_tail(self, job_name: str, namespace: str, lines: int = 40) -> list[str]:
        _, core = self._clients()
        pods = core.list_namespaced_pod(namespace=namespace, label_selector="app=kilvin-trainer").items
        pods = [p for p in pods if (p.metadata.labels or {}).get("job-name") == job_name]
        if not pods:
            return []
        try:
            text = core.read_namespaced_pod_log(
                name=pods[-1].metadata.name,
                namespace=namespace,
                tail_lines=lines,
            )
        except Exception as err:
            return [f"<no logs: {err}>"]
        return text.splitlines()[-lines:]
