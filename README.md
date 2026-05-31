# Temporalis Control Repo

This workspace root is a lightweight control repo for the Temporal multi-repo workspace that sits beside the managed upstream repos.

The control layer does three things:

- defines the curated repo set in `.monorepo/repos.yaml`
- records the latest observed workspace state in `.monorepo/current.lock.json`
- provides `./.monorepo/monoctl` to inspect drift, validate expectations, and write human-readable snapshots

## Managed repos

- `temporal`
- `cli`
- `sdk-core`
- `sdk-go`
- `sdk-python`
- `sdk-rust`

## Common commands

```bash
make monorepo-init
make monorepo-list
make monorepo-status
make monorepo-doctor
make monorepo-snapshot
```

`./.monorepo/monoctl init` clones missing managed repos from their configured SSH remotes and
fast-forward pulls existing clean repos on their expected branch. It fails without mutating when
an existing repo is dirty, on the wrong branch, detached, or has an unexpected remote.

`./.monorepo/monoctl doctor` is intentionally read-only. It reports drift such as dirty worktrees, branch mismatches, missing remotes, and missing repos, but it does not mutate the managed subrepos.

## Inspectl
`inspectl` is a local-first facade for state-threaded Python pipelines that uses Temporal underneath. `run(...)` boots or connects to a local Temporal dev server when needed.

Public API:

- `@step`
- `@pipeline`
- `run(...)`
- `inspectl ...`

See [docs/inspectl/README.md](docs/inspectl/README.md) for the quickstart and debugging workflow.

## Temporal Explorer

`explorer/` is a local React app that explains how a Kilvin-inspired Python asyncio workflow moves through sdk-python, the Python bridge, sdk-core, and Temporal server.

The explorer is backed by the root [HACKERS_GUIDE.md](HACKERS_GUIDE.md), generated manifests under `explorer/public/data/`, and deterministic teaching probes in `hacks/`.
It includes a rendered Hacker's Guide family alongside the Lifecycle Deep Dive and Control Paths views.

Start with:

- `HACKERS_GUIDE.md`: canonical narrative for the happy path, control paths, source refs, and paired hack scripts.
- `hacks/001_source_map.py`: prints the source anchors used by the guide and explorer.
- `hacks/002_lifecycle_manifest.py`: walks the Kilvin asyncio happy-path manifest in guide order.

The remaining default hacks cover task queue polling, history/replay, and control-path overlays. `hacks/006_optional_local_run.py` is explicitly opt-in and is not part of the default verification path because it may require local Temporal runtime prerequisites.

Common commands:

```bash
make explorer-gen-data
make explorer-build
make explorer-dev
```

`make explorer-gen-data` regenerates the static guide, lifecycle, control-path, and repo manifests from the initialized workspace. `make explorer-build` runs the explorer production build workflow, and `make explorer-dev` starts the local Vite development server.

The generator reads the initialized managed repos and writes static JSON under `explorer/public/data/`. Run `make monorepo-init` and confirm `make monorepo-doctor` passes before regenerating explorer data.
