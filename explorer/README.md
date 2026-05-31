# Temporal Explorer

Interactive Observatory-style explorer for understanding how a Kilvin-inspired Python asyncio workflow runs through Temporal.

The explorer is guide-backed: root `../HACKERS_GUIDE.md` is the canonical narrative source, `../hacks/NNN_*.py` contains the paired runnable probes, and generated JSON in `public/data/` connects guide anchors, hack metadata, source refs, lifecycle phases, and control-path overlays.

## Modes

- Lifecycle Deep Dive: happy-path mental model from client start through server history, task queues, sdk-core polling, Python workflow activation, activity execution, and completions. Each phase links to its `HACKERS_GUIDE.md` section, matching hack command, and source refs.
- Control Paths: overlays for pause/resume, retry, replay, heartbeat cancellation, and sticky-cache eviction. Each scenario explains the ownership boundary and links to the relevant guide section and hack script.

## Commands

```bash
./scripts/workflow.sh gen-data
./scripts/workflow.sh install
./scripts/workflow.sh build
./scripts/workflow.sh dev
```

Use `gen-data` after changing `../HACKERS_GUIDE.md`, `../hacks`, managed repo source refs, or lifecycle/control manifest inputs. Use `build` for the full explorer verification workflow and `dev` for the local Vite server.

The root Makefile wraps the common commands as `make explorer-gen-data`, `make explorer-build`, and `make explorer-dev`.
