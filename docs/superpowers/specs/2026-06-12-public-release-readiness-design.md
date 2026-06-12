# Public Release Readiness Design

Status: approved 2026-06-12 through brainstorming in this thread. This spec turns Temporalis into a polished public teaching/open-source repo that is easy to spin up and honest about what each layer proves.

## Goal

Make Temporalis ready for general release as a teaching repo for durable machine-learning training and Temporal internals.

The public experience should let a new user:

- Open a hosted explorer and learn the story without installing anything.
- Clone the repo and run a lightweight local path quickly.
- Opt into the full local runtime proof when they want to see Temporal, the Kilvin workflow, the allocator, docker image materialization, and k3s execution working together.

The repo should feel public, coherent, and maintainable: current docs, stable commands, CI-backed confidence, no stale Hacker's Guide UI references, no hidden release knowledge in `.agent/`, and no accidental local artifacts presented as product.

## Non-Goals

- Do not make the live docker/k3s runtime mandatory for every user.
- Do not remove `HACKERS_GUIDE.md`; the guide can remain as source/provenance even though it is no longer an in-app Deep Dive track.
- Do not add new production dependencies just for release polish.
- Do not turn this repo into production ML infrastructure. The public promise is teaching and local proof, not a multi-tenant training platform.
- Do not publish automatically from a local command without an explicit release/push step.

## Release Experience

The repo exposes three layers.

### Tier 0: Hosted Explorer

The fastest path is the GitHub Pages explorer. The README should lead with the hosted URL and explain that this is the best way to inspect the Temporal lifecycle, control paths, and Kilvin internals without local setup.

The hosted page is a teaching instrument, not a marketing page. It should emphasize the one narrative: a request to train model X on FineWeb with 64 A100 GPUs, then show how the repo maps that production-shaped intent to a laptop-scale implementation.

### Tier 1: Lightweight Local Teaching Path

The clone-and-run path should be quick and deterministic. It should not require docker, k3s, a live Temporal server, or cloud credentials.

This layer should validate generated explorer data, source-grounded Temporal refs, deterministic hack/probe scripts, and the explorer app. It should then start or point to the local explorer so users can learn by clicking through the diagrams.

The README should describe this as "learn and verify the model" rather than "run the whole training system."

### Tier 2: Full Runtime Proof

The advanced path is the real local Kilvin runtime: Temporal server, worker, allocator, local registry, docker image build/push, k3s Job submission, monitoring, artifacts, and Temporal UI inspection.

This path remains optional because it depends on local docker/Colima capacity and takes longer. It is the proof that the teaching model corresponds to a real workflow, not the prerequisite for understanding the repo.

## Commands And Gates

Add stable top-level Make targets that encode the three layers.

### `make quickstart`

`quickstart` is the Tier 1 entrypoint. It should:

- Run the focused generated-data/source-grounding checks.
- Run deterministic teaching probes.
- Verify the explorer can build or run locally.
- Print the local explorer URL and the recommended first pages.

The command may start the explorer dev server if that fits the existing tooling cleanly. If a long-running dev server makes automation awkward, split the behavior into a check target plus a clearly printed `make explorer-dev` next step.

### `make verify-release`

`verify-release` is the release gate for normal CI-safe work. It should include:

- workspace/monorepo doctor checks that do not require live runtime side effects;
- explorer data generation;
- explorer source-grounding tests;
- hack/probe tests;
- explorer unit tests;
- explorer typecheck;
- production explorer build.

This target should avoid Tier 2 live runtime requirements so it can run consistently in local and CI contexts.

### `make runtime-proof`

`runtime-proof` is the Tier 2 proof. It should wrap or alias the real Kilvin smoke path from the operator kit, preserving the current detailed diagnostics. This target can remain opt-in and may document expected local prerequisites.

## Documentation

The public README becomes the primary onboarding page. It should cover:

- what Temporalis teaches;
- the hosted explorer URL;
- the three execution layers;
- the quickstart commands;
- what users will learn about Temporal and durable ML training;
- what the repo deliberately does not promise.

Add or update:

- `docs/quickstart.md`: clone-to-learning path, Tier 0 and Tier 1.
- `docs/runtime-proof.md`: Tier 2 path, derived from the Kilvin runbook but framed for public users.
- `docs/release-checklist.md`: maintainer gate before push/publish.
- `docs/source-grounding.md`: how generated explorer refs are pinned to upstream Temporal/server, SDK Core, SDK Python, and Temporal UI source.
- `explorer/README.md`: current explorer architecture, with Basics plus Deep Dive Lifecycle, Control Paths, and Kilvin Internals only.

The docs should remove stale statements that the in-app Deep Dive contains a Hacker's Guide tab or guide-section navigation.

## Explorer Product Surface

The explorer remains the centerpiece. It should stay technical and dense enough for repeated inspection.

Release polish should prioritize:

- current copy that matches the simplified Deep Dive UI;
- direct upstream source refs in Lifecycle and Control Paths;
- Kilvin Internals copy aligned with Basics: model-X/FineWeb intent, dependency build, quota/allocation, materialized job spec, k8s submit, monitoring, and laptop-scale execution;
- source/probe CTAs rather than hidden guide navigation;
- responsive layout checks for Basics and each Deep Dive track.

The Hacker's Guide can remain in the repo as an authored deep reference, but it should not appear as a primary app mode, footer promise, or required path through the UI.

## CI And Release Verification

Add a normal CI workflow that exercises the CI-safe release gate. It should run on pull requests and pushes to `phi9t-mainline` unless the project later renames its release branch.

The existing GitHub Pages deploy workflow remains separate. A post-publish verification target should prove that hosted explorer data has updated when publishing matters.

Acceptance checks:

- Fresh clone instructions are sufficient for Tier 0 and Tier 1.
- `make verify-release` passes on a development machine with the normal Python/Node prerequisites.
- GitHub Pages serves the generated explorer bundle after publish.
- There are no stale in-app or README claims about a visible Hacker's Guide track.
- Public docs distinguish teaching model, local proof, and non-production boundaries.

## Agent Artifacts And Public Hygiene

`.agents/` is the durable home for repo-local agent material. `.agent/` is transient scratch.

Release prep should audit `.agent/` and move useful durable material into the right public place:

- Reusable agent skills and instructions go under `.agents/skills/`.
- Reusable agent notes may go under `.agents/notes/` if they are safe, durable, and helpful.
- Human-facing verifiers should become `scripts/` plus Make targets rather than living only under `.agents/`.
- Session-only learning notes should be harvested into docs/specs if they contain useful decisions, then removed from `.agent/`.

For the current repo state, `.agent/control_path_check.py` should move to `.agents/checks/control_path_check.py` as a durable agent utility because it is a live-control helper rather than the general public quickstart. If it later becomes part of the public release gate, wrap or promote it under `scripts/` with a Make target. `.agent/LEARNING_SESSION.md` should be harvested into public docs/specs for durable decisions, then moved to `.agents/notes/release-learning-session.md` only if the remaining note is still safe and useful. No canonical release knowledge should remain only under `.agent/`.

Release hygiene should also cover:

- ignored local runtime artifacts;
- generated build outputs;
- local upstream checkouts;
- accidental scratch files;
- private/internal wording that does not belong in a public teaching repo.

## Error Handling And Honesty

The public surface should be clear when a command is unavailable or a local prerequisite is missing.

- Tier 1 failures should point to missing Python/Node prerequisites or broken generated data, not docker/k3s.
- Tier 2 failures should point to the existing Kilvin doctor/runbook diagnostics.
- Docs should say when a command starts a long-running server.
- Docs should say when runtime proof is laptop-scale and CPU-oriented even though the narrative begins with a production-shaped 64-A100/FineWeb request.

## Testing Plan

Focused validation for implementation:

- `make quickstart` or its check-only equivalent.
- `make verify-release`.
- Existing generated-data tests, including pinned upstream source refs.
- Explorer unit tests and typecheck.
- `make explorer-build`.
- `make runtime-proof` when local docker/Colima/k3s prerequisites are available.
- Browser spot checks for the hosted/local explorer after significant frontend/docs changes.

The final release should document any Tier 2 validation that was skipped because local runtime prerequisites were unavailable.

## Acceptance Criteria

- A public reader can understand the repo purpose from the first screen of the README.
- A public reader can use the hosted explorer without cloning.
- A public reader can clone and complete the lightweight local path without live Temporal infrastructure.
- An advanced user can follow the full runtime proof path and understand what evidence proves success.
- Docs, explorer copy, and generated data tell the same story.
- `.agent/` contains no durable release knowledge; durable agent-facing material lives under `.agents/` or is promoted to human-facing scripts/docs.
- CI and Make targets encode the intended release gates.
- No unrelated local artifacts are staged or published.
