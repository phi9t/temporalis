from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kilvin-py"))

from kilvin_py.config import KilvinSettings  # noqa: E402
from kilvin_py.proc import SubprocessFailed, run_logged  # noqa: E402
from kilvin_py.activities import docker_build_command  # noqa: E402
from kilvin_py.allocator_client import (  # noqa: E402
    AllocatorClient,
    AllocatorUnavailable,
    QuotaExhausted,
)
from kilvin_py.k8s_manifest import render_job_manifest  # noqa: E402


def test_settings_defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = KilvinSettings.load()
    assert settings.temporal_address == "localhost:7233"
    assert settings.allocator_url == "http://localhost:7070"
    assert settings.registry == "localhost:5001"
    assert settings.namespace == "kilvin-training"
    assert settings.trainer_dir.name == "trainer"
    assert settings.kubeconfig_path.name == "kubeconfig.yaml"

    monkeypatch.setenv("KILVIN_ALLOCATOR_URL", "http://allocator:7070")
    assert KilvinSettings.load().allocator_url == "http://allocator:7070"


def test_run_logged_captures_output_and_raises_with_tail() -> None:
    lines = asyncio.run(run_logged([sys.executable, "-c", "print('a'); print('b')"], label="ok"))
    assert lines == ["a", "b"]

    with pytest.raises(SubprocessFailed) as err:
        asyncio.run(
            run_logged(
                [sys.executable, "-c", "print('boom-detail'); raise SystemExit(3)"],
                label="fails",
            )
        )
    assert "boom-detail" in str(err.value)
    assert "exit 3" in str(err.value)


def test_docker_build_command_adds_host_resolved_package_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    addresses = {
        "files.pythonhosted.org": "167.82.0.223",
        "download.pytorch.org": "99.84.141.46",
        "download-r2.pytorch.org": "104.18.8.52",
        "pypi.org": "151.101.0.223",
    }
    monkeypatch.setattr("kilvin_py.activities.socket.gethostbyname", addresses.__getitem__)

    command = docker_build_command("localhost:5001/kilvin-trainer:run-a")

    assert command[:2] == ["docker", "build"]
    for host, address in addresses.items():
        assert ["--add-host", f"{host}:{address}"] == command[
            command.index(f"{host}:{address}") - 1 : command.index(f"{host}:{address}") + 1
        ]
    assert command[-3:] == ["-t", "localhost:5001/kilvin-trainer:run-a", "."]


def _client_with(handler) -> AllocatorClient:
    return AllocatorClient("http://allocator.test", transport=httpx.MockTransport(handler))


def test_allocator_client_returns_grant() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/allocations"
        return httpx.Response(
            200,
            json={
                "allocation_id": "alloc-1",
                "cluster": "local-k3s",
                "cpus_granted": 2,
                "memory_gb_granted": 4,
                "quota_decision": {"cluster": "local-k3s", "reason": "fits"},
            },
        )

    grant = asyncio.run(
        _client_with(handler).request_allocation(run_id="r", stage_id="pretrain", cpus=2, memory_gb=4)
    )
    assert grant.allocation_id == "alloc-1"
    assert grant.quota_decision["reason"] == "fits"


def test_allocator_client_maps_409_and_connect_errors() -> None:
    def exhausted(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "quota exhausted on local-k3s"})

    with pytest.raises(QuotaExhausted, match="quota exhausted"):
        asyncio.run(
            _client_with(exhausted).request_allocation(run_id="r", stage_id="s", cpus=9, memory_gb=1)
        )

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(AllocatorUnavailable, match="run kilvin-py/infra/up.sh"):
        asyncio.run(
            _client_with(unreachable).request_allocation(run_id="r", stage_id="s", cpus=1, memory_gb=1)
        )


def test_allocator_client_release() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/v1/allocations/alloc-1"
        return httpx.Response(200, json={"released": "alloc-1"})

    asyncio.run(_client_with(handler).release("alloc-1"))


def test_render_job_manifest_is_the_literal_launch_spec() -> None:
    manifest = render_job_manifest(
        job_name="kilvin-pretrain-abc123",
        namespace="kilvin-training",
        image="localhost:5001/kilvin-trainer@sha256:deadbeef",
        env={"MAX_STEPS": "200", "MODEL_NAME": "model-x"},
        cpus=2,
        memory_gb=4,
        run_id="run-a",
        stage_id="pretrain",
    )

    assert manifest["kind"] == "Job"
    assert manifest["metadata"]["namespace"] == "kilvin-training"
    assert manifest["metadata"]["labels"]["kilvin.run-id"] == "run-a"
    spec = manifest["spec"]
    assert spec["backoffLimit"] == 0
    pod = spec["template"]["spec"]
    assert pod["restartPolicy"] == "Never"
    container = pod["containers"][0]
    assert container["image"].endswith("@sha256:deadbeef")
    assert {"name": "MAX_STEPS", "value": "200"} in container["env"]
    assert container["resources"]["requests"]["cpu"] == "2"
    assert container["resources"]["limits"]["memory"] == "4Gi"
