# Temporalis Agent Guide

This repo is a teaching-oriented Temporal workspace. Code changes should make the
system more correct and make the relevant Temporal, Kilvin, or local tooling
behavior easier for the human to explain afterward.

## Repo Map

- `monoctl/` and `.monorepo/`: workspace control tooling for managed Temporal
  repos, drift checks, and snapshots.
- `inspectl/`: local-first Python pipeline facade backed by Temporal concepts
  such as durable runs, retries, pause/resume, logs, and state snapshots.
- `explorer/`: React teaching app — Basics, Deep Dive (lifecycle + control
  paths), and Hacker's Guide views, all themed around one request: train
  model X on FineWeb with 64 A100 GPUs.
- `kilvin-py/`: the runnable Temporal Python implementation of that training
  launch (parent/child workflows, activities, hood-open YAML artifacts).
- `hacks/`: deterministic teaching probes that connect the guide and generated
  explorer data to source-grounded examples.
- `docs/superpowers/specs/`: design specs for major features.
- `docs/superpowers/plans/`: detailed implementation plans for larger work.
- `tests/`: Python tests for workspace tooling, inspectl, hacks, and generated
  explorer data.

## Common Commands

- Python tests: `PYTHONPATH=. pytest -q`
- Root test target: `make test`
- Workspace status: `make monorepo-status`
- Workspace doctor: `make monorepo-doctor`
- Explorer data generation: `make explorer-gen-data`
- Explorer production build: `make explorer-build`
- Explorer dev server: `make explorer-dev`

Use focused commands first, then broader checks when the change affects shared
behavior or generated explorer data.

## Operating Modes

Default to concise teaching for non-trivial work. Explain the problem, the code
path, the chosen fix, and the validation in concrete repo terms.

Use interactive teaching when the task is primarily about understanding Temporal
or Kilvin behavior, when the user asks to learn deeply, or when a change touches
complex control flow such as replay, retries, pause/resume, task queue polling,
activity heartbeats, sticky cache behavior, or generated explorer manifests.

Use autonomous execution for small, mechanical, or low-risk edits. Do not block
on questions that can be answered by reading the repo. Record assumptions in the
final response when they affect correctness.

Do not introduce new production dependencies, public APIs, schema changes,
migrations, authentication changes, authorization changes, data deletion, or
security-sensitive behavior without calling out the risk and getting explicit
confirmation unless the user already requested that exact change.

## Teaching Workflow

Before changing code, inspect the relevant implementation, tests, and existing
design docs. Prefer `rg` and focused file reads.

For substantial or education-heavy tasks, create or update
`.agent/LEARNING_SESSION.md`. Keep it local; `.agent/` is ignored. Include:

- task and current subsystem
- repo findings and files inspected
- current understanding, assumptions, and missing details
- design decision log and rejected alternatives
- validation commands and results
- final teach-back questions

For simple fixes, a clear final summary plus test results is enough.

When teaching, make the codebase legible:

- identify entry points, data models, state transitions, and ownership
  boundaries
- name the branches, flags, roles, or failure modes that matter
- explain what would fail if the chosen invariant were broken
- connect explorer UI behavior back to generated manifests and guide/hack data
- use short checkpoints or teach-back questions when the user wants active
  learning

Do not reveal quiz answers before the user answers when a quiz is explicitly in
progress.

## Implementation Guidance

Keep changes small and idiomatic. Follow existing local style before inventing a
new abstraction.

Prefer additive manifest/schema changes for explorer data. Keep lifecycle
topology stable unless the task explicitly requires changing it.

For `inspectl`, preserve the local-first mental model: explicit pipeline state,
readable step transitions, inspectable logs, and Temporal-backed durability
hidden behind simple APIs.

For frontend work, keep the explorer usable as a technical instrument: dense
enough for repeated inspection, visually restrained, and consistent with the
existing components in `explorer/src`.

For docs and teaching probes, keep source anchors, guide headings, generated
manifest data, and tests aligned. Update `HACKERS_GUIDE.md`, `hacks/`, data
generation, and explorer tests together when a feature depends on all of them.

## Validation Expectations

Choose the narrowest meaningful validation first:

- `monoctl` or workspace tooling: targeted `tests/test_*.py`, then
  `make monorepo-doctor` when workspace state matters.
- `inspectl`: focused `tests/inspectl/...`, plus integration tests when runtime
  behavior changes.
- `hacks` or guide metadata: `PYTHONPATH=. pytest -q tests/hacks/test_hacks.py`
  and relevant explorer data tests.
- Explorer UI: `npm test`, `npm run typecheck`, or `make explorer-build` from
  the appropriate scope, depending on the change.
- Generated data: run `make explorer-gen-data` when inputs or generator logic
  change.

Never claim verification ran unless it actually ran. If a check cannot be run,
state why and what risk remains.

## Final Response

For coding tasks, summarize:

- problem or intended behavior
- root cause when applicable
- solution and important files changed
- validation commands and results
- user/product impact and remaining risk

For teaching-oriented tasks, also include a short teach-back prompt or quiz
without answers.
