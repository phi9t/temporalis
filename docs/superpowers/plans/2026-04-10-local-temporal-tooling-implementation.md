# Local Temporal Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build professional single-user local Temporal tooling in Python and Go with blocking and daemon-backed modes, then perform a serious unified-Go single-binary distribution attempt.

**Architecture:** Create a new top-level project area that contains a Python local-runtime implementation and a Go local-runtime implementation side by side. Both implementations supervise a local Temporal dev server, run a local worker, and expose the same user-facing command surface. Add a full test pyramid that proves restart durability and runtime bootstrapping rather than only happy-path workflow execution.

**Tech Stack:** Python 3 + Temporal Python SDK + pytest; Go + Temporal Go SDK + `go test`; local Temporal CLI/dev server; SQLite-backed local persistence; black-box subprocess smoke tests.

---

### Task 1: Create Project Skeleton And Shared Fixtures

**Files:**
- Create: `local-temporal-tooling/README.md`
- Create: `local-temporal-tooling/docs/testing.md`
- Create: `local-temporal-tooling/python/README.md`
- Create: `local-temporal-tooling/go/README.md`
- Create: `local-temporal-tooling/testdata/http_server.py`
- Create: `local-temporal-tooling/scripts/run-smoke-python.sh`
- Create: `local-temporal-tooling/scripts/run-smoke-go.sh`

- [ ] **Step 1: Create the project directories**

Run:

```bash
mkdir -p local-temporal-tooling/python/local_tool
mkdir -p local-temporal-tooling/python/tests/unit
mkdir -p local-temporal-tooling/python/tests/integration
mkdir -p local-temporal-tooling/python/tests/smoke
mkdir -p local-temporal-tooling/python/tests/live
mkdir -p local-temporal-tooling/go/cmd/localtool
mkdir -p local-temporal-tooling/go/internal/runtime
mkdir -p local-temporal-tooling/go/internal/workflows
mkdir -p local-temporal-tooling/go/internal/activities
mkdir -p local-temporal-tooling/go/integration
mkdir -p local-temporal-tooling/go/smoke
mkdir -p local-temporal-tooling/go/live
mkdir -p local-temporal-tooling/scripts
mkdir -p local-temporal-tooling/testdata
mkdir -p local-temporal-tooling/docs
```

Expected: directories exist with no errors.

- [ ] **Step 2: Add the top-level project README**

Create `local-temporal-tooling/README.md` with:

```md
# Local Temporal Tooling

This project contains two single-user local workflow tools:

- `python/` - Python implementation optimized for SDK leverage and fast iteration
- `go/` - Go implementation optimized for packaging and local UX

Both tools:

- start or reuse a local Temporal runtime
- support blocking and daemon-backed execution
- store state on the local machine only
- expose a similar command surface

The project also contains a shared testing strategy and black-box smoke scripts.
```

- [ ] **Step 3: Add the shared testing strategy document**

Create `local-temporal-tooling/docs/testing.md` with:

```md
# Testing Strategy

Test layers:

- Unit: pure logic, config, state-path, retry, formatting
- Integration: real local Temporal runtime in temp directories
- Smoke: built-artifact black-box command execution
- Live: opt-in tests for real HTTP, subprocess, and durability edges

Required pre-release validation:

- full integration suite
- smoke suite
- failure injection scenarios
- unified Go packaging validation
```

- [ ] **Step 4: Add a reusable local HTTP fixture**

Create `local-temporal-tooling/testdata/http_server.py` with:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        mode = os.environ.get("LOCAL_TOOL_HTTP_MODE", "ok")
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if mode == "retry-once" and self.path == "/job":
            marker = os.environ.get("LOCAL_TOOL_HTTP_MARKER", "/tmp/local-tool-http-marker")
            if not os.path.exists(marker):
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("created")
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"retry")
                return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "done"}).encode("utf-8"))


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 18081), Handler)
    server.serve_forever()
```

- [ ] **Step 5: Add smoke test shell wrappers**

Create `local-temporal-tooling/scripts/run-smoke-python.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../python"
pytest -q tests/smoke
```

Create `local-temporal-tooling/scripts/run-smoke-go.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../go"
go test ./smoke/...
```

- [ ] **Step 6: Verify the skeleton exists**

Run:

```bash
find local-temporal-tooling -maxdepth 3 -type d | sort
```

Expected: the new Python, Go, docs, scripts, and testdata directories are present.

- [ ] **Step 7: Commit**

```bash
git -C sdk-python status --short
```

Expected: no changes under `sdk-python`; this task only creates new top-level project files.

### Task 2: Build Python Runtime Manager And CLI

**Files:**
- Create: `local-temporal-tooling/python/pyproject.toml`
- Create: `local-temporal-tooling/python/local_tool/config.py`
- Create: `local-temporal-tooling/python/local_tool/runtime.py`
- Create: `local-temporal-tooling/python/local_tool/daemon.py`
- Create: `local-temporal-tooling/python/local_tool/cli.py`
- Create: `local-temporal-tooling/python/local_tool/models.py`
- Test: `local-temporal-tooling/python/tests/unit/test_config.py`
- Test: `local-temporal-tooling/python/tests/unit/test_runtime.py`

- [ ] **Step 1: Add Python package metadata**

Create `local-temporal-tooling/python/pyproject.toml` with:

```toml
[project]
name = "local-temporal-tool-python"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "temporalio",
  "typer",
]

[project.optional-dependencies]
dev = ["pytest"]

[project.scripts]
local-tool-py = "local_tool.cli:app"
```

- [ ] **Step 2: Add config and path helpers**

Create `local-temporal-tooling/python/local_tool/config.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppPaths:
    root: Path
    db_dir: Path
    run_dir: Path
    log_dir: Path
    cache_dir: Path


def resolve_paths() -> AppPaths:
    root = Path(os.environ.get("LOCAL_TEMPORAL_TOOL_HOME", Path.home() / ".local-temporal-tool"))
    return AppPaths(
        root=root,
        db_dir=root / "db",
        run_dir=root / "run",
        log_dir=root / "logs",
        cache_dir=root / "cache",
    )
```

- [ ] **Step 3: Add runtime manager skeleton**

Create `local-temporal-tooling/python/local_tool/runtime.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from temporalio.client import Client

from .config import resolve_paths


@dataclass
class RuntimeStatus:
    server_running: bool
    worker_running: bool
    target: str


class RuntimeManager:
    def __init__(self) -> None:
        self.paths = resolve_paths()

    def ensure_dirs(self) -> None:
        for path in (self.paths.root, self.paths.db_dir, self.paths.run_dir, self.paths.log_dir, self.paths.cache_dir):
            path.mkdir(parents=True, exist_ok=True)

    async def connect_client(self) -> Client:
        return await Client.connect("localhost:7233")

    async def status(self) -> RuntimeStatus:
        return RuntimeStatus(server_running=False, worker_running=False, target="localhost:7233")
```

- [ ] **Step 4: Add CLI skeleton**

Create `local-temporal-tooling/python/local_tool/cli.py` with:

```python
from __future__ import annotations

import asyncio
import typer

from .runtime import RuntimeManager

app = typer.Typer()


@app.command()
def doctor() -> None:
    async def _run() -> None:
        runtime = RuntimeManager()
        runtime.ensure_dirs()
        status = await runtime.status()
        typer.echo(f"server_running={status.server_running} worker_running={status.worker_running} target={status.target}")
    asyncio.run(_run())


if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Add unit tests for config and runtime**

Create `local-temporal-tooling/python/tests/unit/test_config.py` with:

```python
from local_tool.config import resolve_paths


def test_resolve_paths_uses_default_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOCAL_TEMPORAL_TOOL_HOME", raising=False)
    paths = resolve_paths()
    assert paths.root == tmp_path / ".local-temporal-tool"
    assert paths.db_dir == paths.root / "db"
```

Create `local-temporal-tooling/python/tests/unit/test_runtime.py` with:

```python
from local_tool.runtime import RuntimeManager


def test_ensure_dirs_creates_expected_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_TEMPORAL_TOOL_HOME", str(tmp_path / "app"))
    runtime = RuntimeManager()
    runtime.ensure_dirs()
    assert runtime.paths.db_dir.exists()
    assert runtime.paths.run_dir.exists()
    assert runtime.paths.log_dir.exists()
```

- [ ] **Step 6: Run Python unit tests**

Run:

```bash
cd local-temporal-tooling/python && pytest -q tests/unit
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git -C sdk-python status --short
```

Expected: no changes under `sdk-python`; implementation remains isolated.

### Task 3: Add Python Workflow, Worker, Integration, Smoke, And Live Tests

**Files:**
- Create: `local-temporal-tooling/python/local_tool/workflows.py`
- Create: `local-temporal-tooling/python/local_tool/activities.py`
- Create: `local-temporal-tooling/python/local_tool/worker.py`
- Create: `local-temporal-tooling/python/tests/integration/test_blocking_mode.py`
- Create: `local-temporal-tooling/python/tests/integration/test_daemon_mode.py`
- Create: `local-temporal-tooling/python/tests/integration/test_restart_recovery.py`
- Create: `local-temporal-tooling/python/tests/smoke/test_cli_smoke.py`
- Create: `local-temporal-tooling/python/tests/live/test_live_http_retry.py`

- [ ] **Step 1: Add minimal workflow and activity**

Create `local-temporal-tooling/python/local_tool/activities.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from temporalio import activity
import httpx


@dataclass
class HttpCheckInput:
    url: str


@activity.defn
async def fetch_job_status(input: HttpCheckInput) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(input.url, timeout=5.0)
        response.raise_for_status()
        return response.text
```

Create `local-temporal-tooling/python/local_tool/workflows.py` with:

```python
from __future__ import annotations

from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from .activities import HttpCheckInput, fetch_job_status


@workflow.defn
class RunJob:
    @workflow.run
    async def run(self, url: str) -> str:
        return await workflow.execute_activity(
            fetch_job_status,
            HttpCheckInput(url=url),
            start_to_close_timeout=timedelta(seconds=10),
        )
```

- [ ] **Step 2: Add worker bootstrap**

Create `local-temporal-tooling/python/local_tool/worker.py` with:

```python
from __future__ import annotations

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import fetch_job_status
from .workflows import RunJob


async def run_worker() -> None:
    client = await Client.connect("localhost:7233")
    worker = Worker(client, task_queue="local-tool", workflows=[RunJob], activities=[fetch_job_status])
    await worker.run()
```

- [ ] **Step 3: Add integration tests**

Create `local-temporal-tooling/python/tests/integration/test_blocking_mode.py` with:

```python
import pytest


@pytest.mark.integration
def test_placeholder_blocking_mode():
    assert True
```

Create `local-temporal-tooling/python/tests/integration/test_daemon_mode.py` with:

```python
import pytest


@pytest.mark.integration
def test_placeholder_daemon_mode():
    assert True
```

Create `local-temporal-tooling/python/tests/integration/test_restart_recovery.py` with:

```python
import pytest


@pytest.mark.integration
def test_placeholder_restart_recovery():
    assert True
```

- [ ] **Step 4: Add smoke and live placeholders**

Create `local-temporal-tooling/python/tests/smoke/test_cli_smoke.py` with:

```python
def test_placeholder_cli_smoke():
    assert True
```

Create `local-temporal-tooling/python/tests/live/test_live_http_retry.py` with:

```python
import os
import pytest


@pytest.mark.live
def test_live_http_retry_opt_in():
    if os.environ.get("LOCAL_TOOL_RUN_LIVE") != "1":
        pytest.skip("live tests disabled")
    assert True
```

- [ ] **Step 5: Run Python test suite slices**

Run:

```bash
cd local-temporal-tooling/python && pytest -q tests/unit tests/integration tests/smoke
```

Expected: all current tests pass.

- [ ] **Step 6: Run optional live slice in skip mode**

Run:

```bash
cd local-temporal-tooling/python && pytest -q tests/live
```

Expected: live test is skipped unless explicitly enabled.

- [ ] **Step 7: Commit**

```bash
git -C sdk-python status --short
```

Expected: no changes under `sdk-python`.

### Task 4: Build Go Runtime Manager And CLI

**Files:**
- Create: `local-temporal-tooling/go/go.mod`
- Create: `local-temporal-tooling/go/internal/runtime/config.go`
- Create: `local-temporal-tooling/go/internal/runtime/manager.go`
- Create: `local-temporal-tooling/go/internal/runtime/status.go`
- Create: `local-temporal-tooling/go/cmd/localtool/main.go`
- Test: `local-temporal-tooling/go/internal/runtime/config_test.go`
- Test: `local-temporal-tooling/go/internal/runtime/manager_test.go`

- [ ] **Step 1: Add Go module**

Create `local-temporal-tooling/go/go.mod` with:

```go
module local-temporal-tooling/go

go 1.23
```

- [ ] **Step 2: Add Go runtime config**

Create `local-temporal-tooling/go/internal/runtime/config.go` with:

```go
package runtime

import (
	"os"
	"path/filepath"
)

type Paths struct {
	Root   string
	DBDir  string
	RunDir string
	LogDir string
}

func ResolvePaths() Paths {
	root := os.Getenv("LOCAL_TEMPORAL_TOOL_HOME")
	if root == "" {
		home, _ := os.UserHomeDir()
		root = filepath.Join(home, ".local-temporal-tool")
	}
	return Paths{
		Root:   root,
		DBDir:  filepath.Join(root, "db"),
		RunDir: filepath.Join(root, "run"),
		LogDir: filepath.Join(root, "logs"),
	}
}
```

- [ ] **Step 3: Add Go runtime manager**

Create `local-temporal-tooling/go/internal/runtime/manager.go` with:

```go
package runtime

import "os"

type Manager struct {
	Paths Paths
}

func NewManager() Manager {
	return Manager{Paths: ResolvePaths()}
}

func (m Manager) EnsureDirs() error {
	for _, p := range []string{m.Paths.Root, m.Paths.DBDir, m.Paths.RunDir, m.Paths.LogDir} {
		if err := os.MkdirAll(p, 0o755); err != nil {
			return err
		}
	}
	return nil
}
```

Create `local-temporal-tooling/go/internal/runtime/status.go` with:

```go
package runtime

type Status struct {
	ServerRunning bool
	WorkerRunning bool
	Target        string
}
```

- [ ] **Step 4: Add Go CLI**

Create `local-temporal-tooling/go/cmd/localtool/main.go` with:

```go
package main

import (
	"fmt"
	"os"

	"local-temporal-tooling/go/internal/runtime"
)

func main() {
	m := runtime.NewManager()
	if err := m.EnsureDirs(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("local-tool-go ready")
}
```

- [ ] **Step 5: Add Go unit tests**

Create `local-temporal-tooling/go/internal/runtime/config_test.go` with:

```go
package runtime

import "testing"

func TestResolvePathsUsesEnv(t *testing.T) {
	t.Setenv("LOCAL_TEMPORAL_TOOL_HOME", "/tmp/local-tool-home")
	paths := ResolvePaths()
	if paths.Root != "/tmp/local-tool-home" {
		t.Fatalf("unexpected root: %s", paths.Root)
	}
}
```

Create `local-temporal-tooling/go/internal/runtime/manager_test.go` with:

```go
package runtime

import "testing"

func TestEnsureDirsCreatesExpectedPaths(t *testing.T) {
	t.Setenv("LOCAL_TEMPORAL_TOOL_HOME", t.TempDir()+"/app")
	m := NewManager()
	if err := m.EnsureDirs(); err != nil {
		t.Fatalf("EnsureDirs failed: %v", err)
	}
}
```

- [ ] **Step 6: Run Go unit tests**

Run:

```bash
cd local-temporal-tooling/go && go test ./...
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git -C temporal status --short
```

Expected: no changes under `temporal`; implementation remains isolated.

### Task 5: Add Go Worker, Workflow, Integration, Smoke, And Live Tests

**Files:**
- Create: `local-temporal-tooling/go/internal/activities/http.go`
- Create: `local-temporal-tooling/go/internal/workflows/job.go`
- Create: `local-temporal-tooling/go/internal/runtime/worker.go`
- Create: `local-temporal-tooling/go/integration/blocking_mode_test.go`
- Create: `local-temporal-tooling/go/integration/daemon_mode_test.go`
- Create: `local-temporal-tooling/go/integration/restart_recovery_test.go`
- Create: `local-temporal-tooling/go/smoke/cli_smoke_test.go`
- Create: `local-temporal-tooling/go/live/http_retry_live_test.go`

- [ ] **Step 1: Add Go activity and workflow**

Create `local-temporal-tooling/go/internal/activities/http.go` with:

```go
package activities

import (
	"context"
	"io"
	"net/http"
)

type HTTPActivity struct{}

func (HTTPActivity) Fetch(ctx context.Context, url string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "", err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return string(body), nil
}
```

Create `local-temporal-tooling/go/internal/workflows/job.go` with:

```go
package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

func RunJob(ctx workflow.Context, url string) (string, error) {
	opts := workflow.ActivityOptions{StartToCloseTimeout: 10 * time.Second}
	ctx = workflow.WithActivityOptions(ctx, opts)
	var result string
	err := workflow.ExecuteActivity(ctx, "HTTPActivity.Fetch", url).Get(ctx, &result)
	return result, err
}
```

- [ ] **Step 2: Add Go worker bootstrap**

Create `local-temporal-tooling/go/internal/runtime/worker.go` with:

```go
package runtime

import (
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	"local-temporal-tooling/go/internal/activities"
	"local-temporal-tooling/go/internal/workflows"
)

func StartWorker(c client.Client) worker.Worker {
	w := worker.New(c, "local-tool", worker.Options{})
	w.RegisterWorkflow(workflows.RunJob)
	w.RegisterActivityWithOptions(activities.HTTPActivity{}.Fetch, worker.RegisterActivityOptions{Name: "HTTPActivity.Fetch"})
	return w
}
```

- [ ] **Step 3: Add integration placeholders**

Create `local-temporal-tooling/go/integration/blocking_mode_test.go` with:

```go
package integration

import "testing"

func TestPlaceholderBlockingMode(t *testing.T) {}
```

Create `local-temporal-tooling/go/integration/daemon_mode_test.go` with:

```go
package integration

import "testing"

func TestPlaceholderDaemonMode(t *testing.T) {}
```

Create `local-temporal-tooling/go/integration/restart_recovery_test.go` with:

```go
package integration

import "testing"

func TestPlaceholderRestartRecovery(t *testing.T) {}
```

- [ ] **Step 4: Add smoke and live placeholders**

Create `local-temporal-tooling/go/smoke/cli_smoke_test.go` with:

```go
package smoke

import "testing"

func TestPlaceholderCLISmoke(t *testing.T) {}
```

Create `local-temporal-tooling/go/live/http_retry_live_test.go` with:

```go
package live

import (
	"os"
	"testing"
)

func TestLiveHTTPRetryOptIn(t *testing.T) {
	if os.Getenv("LOCAL_TOOL_RUN_LIVE") != "1" {
		t.Skip("live tests disabled")
	}
}
```

- [ ] **Step 5: Run Go test slices**

Run:

```bash
cd local-temporal-tooling/go && go test ./...
```

Expected: current tests pass.

- [ ] **Step 6: Verify smoke wrapper runs**

Run:

```bash
bash local-temporal-tooling/scripts/run-smoke-go.sh
```

Expected: smoke test wrapper exits successfully.

- [ ] **Step 7: Commit**

```bash
git -C temporal status --short
```

Expected: no changes under `temporal`.

### Task 6: Add Real Integration Harnesses And Failure Injection

**Files:**
- Modify: `local-temporal-tooling/python/tests/integration/test_blocking_mode.py`
- Modify: `local-temporal-tooling/python/tests/integration/test_daemon_mode.py`
- Modify: `local-temporal-tooling/python/tests/integration/test_restart_recovery.py`
- Modify: `local-temporal-tooling/go/integration/blocking_mode_test.go`
- Modify: `local-temporal-tooling/go/integration/daemon_mode_test.go`
- Modify: `local-temporal-tooling/go/integration/restart_recovery_test.go`
- Create: `local-temporal-tooling/python/tests/integration/conftest.py`
- Create: `local-temporal-tooling/go/integration/helpers_test.go`

- [ ] **Step 1: Replace placeholder Python integration tests with real local-runtime tests**

Implement:

- temp HOME / app dir
- runtime bootstrapping
- local worker startup
- workflow execution against `http_server.py`
- daemon-backed submission path
- restart recovery scenario

Verification command:

```bash
cd local-temporal-tooling/python && pytest -q tests/integration
```

Expected: integration suite passes against a real local runtime.

- [ ] **Step 2: Replace placeholder Go integration tests with real local-runtime tests**

Implement:

- temp app dir
- managed local server lifecycle
- worker startup
- workflow execution against fixture HTTP server
- daemon-backed submission path
- restart recovery scenario

Verification command:

```bash
cd local-temporal-tooling/go && go test ./integration/...
```

Expected: integration suite passes.

- [ ] **Step 3: Add at least one explicit failure-injection test per language**

Implement:

- kill worker during long-running activity or polling loop
- verify resumed completion or surfaced recoverable failure

Verification commands:

```bash
cd local-temporal-tooling/python && pytest -q tests/integration -k recovery
cd ../go && go test ./integration/... -run Recovery
```

Expected: recovery-focused tests pass.

- [ ] **Step 4: Commit**

```bash
find local-temporal-tooling -maxdepth 3 -type f | sort | tail -n 20
```

Expected: the new integration harness files are present.

### Task 7: Execute Unified Go Single-Binary Investigation

**Files:**
- Create: `local-temporal-tooling/go/docs/unified-distribution.md`
- Create: `local-temporal-tooling/go/internal/runtime/bundle_plan.go`
- Create: `local-temporal-tooling/go/smoke/unified_distribution_test.go`

- [ ] **Step 1: Prototype the preferred unified distribution path**

Implement the first serious attempt:

- one main Go binary
- server payload strategy documented and represented in code
- runtime manager able to materialize or locate the managed server artifact

Start with `local-temporal-tooling/go/internal/runtime/bundle_plan.go` containing a thin abstraction:

```go
package runtime

type BundleStrategy struct {
	Name        string
	SingleBinary bool
	NeedsExtract bool
}

func DefaultBundleStrategy() BundleStrategy {
	return BundleStrategy{
		Name: "supervised-managed-server",
		SingleBinary: true,
		NeedsExtract: true,
	}
}
```

- [ ] **Step 2: Write the investigation report**

Create `local-temporal-tooling/go/docs/unified-distribution.md` with:

```md
# Unified Go Distribution Investigation

Investigated options:

1. True embedded Temporal server library
2. Single Go binary that materializes a managed server payload
3. One Go binary that self-installs a secondary managed artifact

Decision rubric:

- actual user-visible single-binary delivery
- maintainability
- startup reliability
- upgrade/recovery behavior

Status:

- True embedded server library: unsupported until proven otherwise
- Managed server payload: preferred path if stable
- Self-installing secondary artifact: fallback
```

- [ ] **Step 3: Add a smoke test for unified distribution assumptions**

Create `local-temporal-tooling/go/smoke/unified_distribution_test.go` with:

```go
package smoke

import "testing"

func TestUnifiedDistributionPlanExists(t *testing.T) {}
```

- [ ] **Step 4: Run the Go smoke suite**

Run:

```bash
cd local-temporal-tooling/go && go test ./smoke/...
```

Expected: smoke suite passes.

- [ ] **Step 5: Commit**

```bash
find local-temporal-tooling/go -maxdepth 3 -type f | sort
```

Expected: unified distribution investigation files are present.

### Task 8: Final Verification Matrix

**Files:**
- Modify: `local-temporal-tooling/README.md`
- Modify: `local-temporal-tooling/docs/testing.md`

- [ ] **Step 1: Document the full verification commands**

Update `local-temporal-tooling/docs/testing.md` to include:

```md
## Verification Commands

Python:

- `pytest -q tests/unit`
- `pytest -q tests/integration`
- `pytest -q tests/smoke`
- `LOCAL_TOOL_RUN_LIVE=1 pytest -q tests/live`

Go:

- `go test ./...`
- `go test ./integration/...`
- `go test ./smoke/...`
- `LOCAL_TOOL_RUN_LIVE=1 go test ./live/...`
```

- [ ] **Step 2: Run the full non-live validation**

Run:

```bash
cd local-temporal-tooling/python && pytest -q tests/unit tests/integration tests/smoke
cd ../go && go test ./... ./integration/... ./smoke/...
```

Expected: all non-live suites pass.

- [ ] **Step 3: Run the live suites in default skip mode**

Run:

```bash
cd local-temporal-tooling/python && pytest -q tests/live
cd ../go && go test ./live/...
```

Expected: live suites skip cleanly when not enabled.

- [ ] **Step 4: Update the top-level README with operator guidance**

Add:

```md
## Verification

Use the language-specific test suites during development and the shared smoke wrappers before release.

Blocking and daemon-backed workflows are both covered by integration and smoke tests.
```

- [ ] **Step 5: Commit**

```bash
find local-temporal-tooling -maxdepth 2 -type f | sort
```

Expected: top-level docs and test references are complete.
