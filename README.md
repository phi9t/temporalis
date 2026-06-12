# Temporalis

Temporalis is a teaching repo for durable machine-learning training with Temporal. It follows one production-shaped request -- train model X on FineWeb with 64 A100 GPUs -- from a high-level intent through workflow history, task queues, retries, replay, source-grounded Temporal internals, and a laptop-scale Kilvin implementation.

Start with the hosted explorer:

https://phi9t.github.io/temporalis/

## Three Ways To Use This Repo

### Tier 0: Hosted Explorer

Open the hosted explorer when you want to learn the system without installing anything. Basics introduces workflows, activities, task queues, history, retry, replay, and hood-open ML training artifacts. Deep Dive then shows Lifecycle, Control Paths, and Kilvin Internals with source-code citations.

### Tier 1: Lightweight Local Teaching Path

Clone the repo, install the normal Python and Node prerequisites, and run:

```bash
make quickstart
./explorer/scripts/workflow.sh install
make explorer-dev
```

This path validates checked-in generated explorer data and deterministic teaching probes. It does not require docker, k3s, cloud credentials, or a live Temporal server.

### Tier 2: Full Runtime Proof

When you want the real local workflow, run:

```bash
make runtime-proof
```

This optional path uses the Kilvin runtime: Temporal, a Python worker, uv+docker image materialization, a local allocator ledger, a local registry, k3s Job submission, monitoring, and artifacts. It proves the teaching model at laptop scale with a tiny CPU GPT trainer rather than a real 64-A100 cluster.

## Workspace Control Layer

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
- `ui`

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
