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

Common commands:

```bash
make explorer-gen-data
make explorer-build
make explorer-dev
```

The generator reads the initialized managed repos and writes static JSON under `explorer/public/data/`. Run `make monorepo-init` and confirm `make monorepo-doctor` passes before regenerating explorer data.
