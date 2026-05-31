# Temporal Kilvin Explorer Design

## Summary

Build `explorer/` as an in-repo Vite/React/TypeScript app for `temporalis`, reusing the
`~/CodeBase/vllm/explorer` Observatory style: dark shell, family switcher, static JSON
manifests, generated source references, clickable SVG diagrams, and sticky detail drawers.

The explorer teaches a deep technical mental model for how a Kilvin-inspired Python asyncio
workflow runs on Temporal. V1 starts with the happy path, then layers in advanced control paths
such as pause/resume, retry, replay, heartbeat cancellation, and sticky-cache eviction. It is a
static, source-grounded teaching tool; it does not execute workflows or collect runtime traces.

## Product Shape

The app has two modes:

- **Lifecycle Deep Dive**: the primary walkthrough. It follows a Kilvin-inspired flow from
  `Client.start_workflow` and Python `Worker.run()` through Temporal Frontend, History, Matching,
  Python bridge APIs, sdk-core pollers/state machines, workflow activations, activity tasks,
  command completion, and history updates.
- **Control Paths**: advanced overlays on the same mental model. Each scenario highlights what
  changes for pause/resume, retry, replay, heartbeat cancellation, worker cache/sticky queues, and
  activity failure recovery.

Both modes include source-backed details across `kilvin-py`, `sdk-python`, `sdk-rust`/`sdk-core`,
and `temporal`. The source drawer is embedded in the walkthrough; V1 is not a full repo browser.

## Data Model And Generation

The React app is a pure reader of generated JSON. Domain knowledge lives in generator scripts under
`explorer/scripts/`.

Generated data:

- `public/data/lifecycle/index.json`: lifecycle subjects. V1 includes
  `kilvin-asyncio-happy-path`.
- `public/data/lifecycle/kilvin-asyncio-happy-path.json`: ordered phases, nodes, edges, callouts,
  and source refs for the happy-path walkthrough.
- `public/data/control-paths/index.json`: switchable control-path scenarios.
- `public/data/control-paths/*.json`: overlays for pause/resume, retry, replay, heartbeat
  cancellation, and sticky-cache eviction.
- `public/data/repos.json`: repo metadata derived from `.monorepo/current.lock.json`, including
  branch, commit, and GitHub blob base for source links.

Core manifest concepts:

- `Phase`: label, short explanation, and included node ids.
- `Node`: id, label, layer, kind, source refs, short summary, and deep-dive notes. Layers are
  `kilvin`, `sdk-python`, `bridge`, `sdk-core`, and `server`.
- `Edge`: from, to, kind, and label. Edge kinds include `rpc`, `poll`, `activation`,
  `completion`, `command`, `history-event`, `task-dispatch`, and `heartbeat`.
- `Scenario`: ordered phase ids plus optional node/edge overlays describing what changes from the
  happy path.

Generators start curated, but source references are resolved by symbol grep against the initialized
local workspace. They must read `.monorepo/current.lock.json` so source links target the recorded
commit, not whatever branch state happens to exist later.

## UI And Interaction

The first screen is the technical walkthrough, not a landing page.

Layout:

- Observatory header/family switcher adapted from `vllm/explorer`, renamed to **Temporal Explorer**.
- Top control row for scenario and phase selection.
- Main grid with an SVG lifecycle diagram on the left and a sticky detail drawer on the right.
- The diagram uses swimlanes for `Kilvin app`, `Python SDK`, `Bridge`, `sdk-core`, and
  `Temporal server`.

Behavior:

- Default selection is the first happy-path phase.
- Phase tabs step through the lifecycle in order.
- Active phase nodes and edges are highlighted; inactive parts are dimmed but still selectable.
- Clicking or keyboard-selecting a node opens details explaining what the layer does, what
  message/object crosses the boundary, and where the implementation lives.
- Control-path scenarios reuse the same diagram vocabulary and overlay changed nodes/edges.

Visual and accessibility constraints:

- Use the Observatory dark/glass visual language, Inter body text, and Fira Code diagram labels.
- Compute SVG node widths from label length; do not hard-code widths that can overflow.
- Every SVG node is keyboard focusable with Enter/Space selection.
- Add reduced-motion guards for any animated flow ticks or transitions.

## Implementation Boundaries

- `explorer/` is self-contained. It may copy/adapt the vLLM explorer kit but must not import from
  `~/CodeBase/vllm`.
- The UI fetches only generated JSON and static assets.
- The app does not require the managed repos at runtime; managed repos are needed only for
  generator runs.
- The source of truth for workspace cleanliness is `./.monorepo/monoctl doctor`.
- The Kilvin narrative is inspired by `kilvin-py`, but the explorer should explain Temporal
  mechanics rather than document every scaffold detail.

## Test And Acceptance Plan

- Generator tests verify key source refs resolve in `kilvin-py`, `sdk-python`, `sdk-rust`, and
  `temporal`.
- Schema tests verify every edge references existing nodes, every phase references existing nodes,
  and every source ref has a repo id/path/line.
- Frontend checks run `npm run typecheck` and `npm run build`.
- Manual acceptance verifies happy-path phase stepping, node selection, source-link rendering,
  control-path overlays, keyboard access, reduced-motion behavior, and no visible label overflow.
- `./.monorepo/monoctl doctor` must pass before generating data.

## Approved Defaults

- App path: `explorer/` inside `/Users/phi9t/CodeBase/temporalis`.
- Style: copy/adapt the `vllm/explorer` Observatory shell and kit patterns.
- V1 priority: happy-path mental model first, then advanced control paths.
- Scope exclusion: no runtime tracing, no workflow execution from the explorer, and no exhaustive
  repo atlas in V1.
