# Temporal Explorer

Interactive teaching app for understanding how a Kilvin-inspired Python asyncio workflow runs through Temporal.

## Modes

- Basics: the model-X/FineWeb training story, workflow concepts, and hood-open artifacts.
- Lifecycle Deep Dive: happy-path calls through the Python client and worker, Python bridge, sdk-core, Temporal server services, task queues, activations, completions, heartbeats, and follow-up workflow tasks.
- Control Paths: overlays for pause/resume, retry, replay, heartbeat cancellation, and sticky-cache eviction.
- Kilvin Internals: the local Kilvin business workflow from intent interpretation through dependency build, quota allocation, materialized job spec, k8s submit, and monitoring.

Lifecycle and Control Paths render direct source/probe panels. The root `../HACKERS_GUIDE.md` remains a source narrative and generator input, but it is not a Deep Dive tab.

## Commands

```bash
./scripts/workflow.sh gen-data
./scripts/workflow.sh install
./scripts/workflow.sh build
./scripts/workflow.sh dev
```

The root Makefile wraps the common commands as `make explorer-gen-data`, `make explorer-build`, and `make explorer-dev`.
