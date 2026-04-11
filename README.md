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
- `ai-cookbook`

## Common commands

```bash
make monorepo-list
make monorepo-status
make monorepo-doctor
make monorepo-snapshot
```

`./.monorepo/monoctl doctor` is intentionally read-only. It reports drift such as dirty worktrees, branch mismatches, missing remotes, and missing repos, but it does not mutate the managed subrepos.

## Inspectl
`inspectl` is a local-first facade for state-threaded Python pipelines that uses Temporal underneath. `run(...)` boots or connects to a local Temporal dev server when needed.

Public API:

- `@step`
- `@pipeline`
- `run(...)`
- `inspectl ...`

See [docs/inspectl/README.md](docs/inspectl/README.md) for the quickstart and debugging workflow.
