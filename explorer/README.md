# Temporal Explorer

Interactive Observatory-style explorer for understanding how a Kilvin-inspired Python asyncio workflow runs through Temporal.

## Modes

- Lifecycle Deep Dive: happy-path mental model from client start through server history, task queues, sdk-core polling, Python workflow activation, activity execution, and completions.
- Control Paths: overlays for pause/resume, retry, replay, heartbeat cancellation, and sticky-cache eviction.

## Commands

```bash
./scripts/workflow.sh gen-data
./scripts/workflow.sh install
./scripts/workflow.sh build
./scripts/workflow.sh dev
```
