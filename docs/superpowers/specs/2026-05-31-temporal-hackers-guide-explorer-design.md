# Temporal Hacker Guide Explorer Design

## Goal

Make the Temporal explorer feel like the vLLM explorer: a guided, source-grounded learning system where the written hacker guide, runnable hack scripts, generated manifests, and interactive explorer all point at the same concepts.

The existing explorer explains the happy path and control paths visually, but it is currently detached from a deeper reading and experimentation path. This design adds a root `HACKERS_GUIDE.md`, a `hacks/` directory of small teaching probes, and guide/script metadata in the existing Lifecycle Deep Dive and Control Paths modes. It does not add a separate guide-rendering mode.

## Audience

The guide targets a hybrid reader, biased toward internals:

- Application engineers should understand how a complex Python asyncio workflow like Kilvin behaves under Temporal.
- Temporal internals readers should see where the server, sdk-core, bridge, and sdk-python each take responsibility.
- The first reading path should be the happy path, then deeper control paths: pause/resume, retry, replay, heartbeat cancellation, and sticky-cache eviction.

## Reference Pattern

The vLLM repository has a root `HACKERS_GUIDE.md`, a `hacks/` directory of runnable subsystem probes, and an explorer whose component deep dive links guide sections, real source refs, and matching scripts. The Temporal version should copy that shape, not the exact UI surface.

Temporal should keep its current two explorer modes:

- `Lifecycle Deep Dive`
- `Control Paths`

The modification is to make those modes guide-backed and script-backed.

## Hacker Guide

Add a root-level `HACKERS_GUIDE.md`. This is the canonical narrative source and should be useful without opening the explorer.

Initial guide spine:

1. How to read this guide
2. 30-second architecture: client, server, Matching, History, Frontend, sdk-core, bridge, Python worker
3. Running example: Kilvin-inspired training workflow
4. Happy path: start workflow to first activation
5. Workflow task polling: Matching -> sdk-core -> bridge -> Python
6. Activity execution and heartbeats
7. History as source of truth and replay
8. Retry and failure handling
9. Pause/resume as signal/update-driven coordination
10. Sticky workflow cache and eviction
11. Where to inspect source next
12. Hands-on hacks

Each deep-dive section should include:

- The user-level event: what Kilvin or sdk-python appears to be doing.
- The Temporal boundary: which API, poll, completion, heartbeat, signal, query, or update boundary is crossed.
- What sdk-core owns: pollers, slot accounting, workflow cache, state machines, activations, completions, heartbeats, retry/cancellation state, and replay mediation.
- What the server owns: namespace/workflow identity, durable history, task queue matching, timers, retry scheduling, and visibility where relevant.
- The deterministic contract: what must replay exactly, what may be side-effecting, and why workflow code, activities, signals, queries, and updates are separated.
- Failure behavior: worker crash, activity timeout, workflow-task failure, retry, sticky miss, cancellation, and replay.
- Source map: concrete references into `temporal`, `sdk-core`, `sdk-python`, and Kilvin files.
- Try it: one matching `hacks/NNN_*.py` script with expected output and what to look for.

The depth bar is high. A section such as workflow task polling should walk History creating a workflow task, Matching handing it to a poller, sdk-core holding the poll loop and slots, the bridge translating core responses into Python objects, sdk-python scheduling an asyncio workflow activation, Python completing commands, core sending completion back, and History appending new events.

## Hacks

Add `hacks/` with zero-padded script names. Scripts should be boring, deterministic teaching probes. The default path should not require a running Temporal server.

Initial scripts:

- `hacks/001_source_map.py`: verifies and prints the key source anchors used by the guide and explorer.
- `hacks/002_lifecycle_manifest.py`: prints happy-path phases, nodes, and edges in guide order.
- `hacks/003_task_queue_polling.py`: walks Matching poll -> sdk-core poller -> bridge -> Python poll loop source refs.
- `hacks/004_history_replay.py`: explains how history events map to replay and activation concepts using generated manifests and source refs.
- `hacks/005_control_paths.py`: prints pause/resume, retry, replay, heartbeat cancellation, and sticky-cache overlays with node/edge explanations.
- `hacks/006_optional_local_run.py`: optional heavier script; starts or assumes a local Temporal dev server and runs a tiny asyncio workflow only if the existing local-runtime path supports it cleanly.

Every hack script should declare lightweight metadata that the generator can read:

```python
GUIDE_ANCHOR = "workflow-task-polling"
SUMMARY = "Trace Matching -> sdk-core -> bridge -> Python workflow activation polling."
```

The optional local-run script must be excluded from default hack verification unless explicitly requested.

## Explorer Integration

Modify the existing two modes. Do not add a third `Hacker Guide` mode.

### Lifecycle Deep Dive

Each lifecycle phase should expose guide context:

- Guide title and anchor.
- Matching hack script path.
- Hack summary.
- Source-backed node refs already present today.

The drawer should gain a `Read / Run / Inspect` block:

- `Read`: link to the matching `HACKERS_GUIDE.md` section anchor.
- `Run`: show the paired hack script path and command.
- `Inspect`: keep existing source refs and line anchors.

The empty drawer should orient the reader toward the learning path: read the current phase, run its hack, then inspect a node.

### Control Paths

Each control scenario should carry the same guide/script metadata plus deeper scenario details. Scenario summaries should explain ownership boundaries, not just name the highlighted nodes.

For example, retry should explain:

- The activity fails or times out in Python.
- sdk-core reports failure/completion state back to the server.
- History records the failure and retry scheduling decision.
- Matching dispatches a new activity task when the retry is due.
- Workflow replay observes durable history rather than re-running prior side effects.

The drawer remains node-focused; the scenario header explains the control-path behavior.

## Data Model

Extend generated lifecycle phases with:

- `guide_anchor`
- `guide_title`
- `hack_script`
- `hack_summary`

Extend generated control scenarios with:

- `guide_anchor`
- `guide_title`
- `hack_script`
- `hack_summary`
- `details`: ordered bullets for the deeper server/sdk-core/Python explanation

Add `explorer/public/data/guide/index.json`, generated from `HACKERS_GUIDE.md`, with enough metadata for the explorer and tests to validate anchors. The explorer does not need to render the guide body.

## Generation

`explorer/scripts/build_lifecycle_data.py` remains the generator entrypoint. The implementation may add a small helper module for guide/hack metadata, but callers should continue to use the existing workflow script and generator entrypoint. The generator should read three inputs:

- Curated lifecycle/control topology.
- Root `HACKERS_GUIDE.md` section anchors.
- `hacks/NNN_*.py` script metadata.

The generator must verify:

- Every lifecycle phase references an existing guide anchor.
- Every control scenario references an existing guide anchor.
- Every referenced hack script exists.
- Every referenced hack script has `GUIDE_ANCHOR` and `SUMMARY`.
- Existing source refs still resolve to real lines.
- Generated guide/script links appear in explorer data.

## Error Handling

Generation should fail loudly for missing guide anchors, missing hack scripts, or missing hack metadata. Runtime explorer loading should keep the existing `AsyncBoundary` behavior and show the generated-data recovery command.

The optional local-run hack should degrade clearly when Temporal runtime prerequisites are absent, but it should not affect default tests or explorer generation.

## Testing

Add or extend Python tests for:

- Guide anchor extraction from `HACKERS_GUIDE.md`.
- Hack metadata extraction from `hacks/NNN_*.py`.
- Lifecycle phase guide/hack link consistency.
- Control scenario guide/hack link consistency.
- Existing source-ref resolution.
- Default hack scripts exiting 0 and printing expected key lines, excluding `006_optional_local_run.py`.

Add or extend frontend tests for:

- A lifecycle phase renders its guide and hack links.
- A control scenario renders details and matching guide/hack links.
- Existing lifecycle/control fetch and overlay behavior continues to work.

Verification commands should include:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py tests/hacks
cd explorer && npm test
cd explorer && npm run lint
./explorer/scripts/workflow.sh build
```

## Non-Goals

- Do not add a new explorer mode for rendering the whole guide.
- Do not make a full Temporal dev-server run mandatory.
- Do not replace the current lifecycle/control diagrams.
- Do not attempt full dynamic tracing from a live Temporal execution in this iteration.
- Do not duplicate large sections of upstream Temporal docs; use source-grounded, Kilvin-driven explanations.

## Success Criteria

- A reader can start at `HACKERS_GUIDE.md`, run paired `hacks/001_*` scripts, then open the explorer and see the same concepts linked from phases, scenarios, and source refs.
- The happy path is the first mental model.
- Advanced behavior is explained as extensions of that happy path.
- Guide anchors, hack scripts, and explorer manifests are validated together.
- The default verification path remains reliable without external services.
