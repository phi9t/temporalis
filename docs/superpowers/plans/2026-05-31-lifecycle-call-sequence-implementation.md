# Lifecycle Call Sequence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class ordered call sequence to the Temporal Explorer lifecycle view so users can understand call order, direction, and messages across the app, SDK, core, and server.

**Architecture:** Extend lifecycle manifests with required `calls`, validate loaded manifests before rendering, and derive phase highlights from call rows instead of phase node lists. Add a focused `CallSequence` component as the timeline spine, update the drawer to support selected calls, and upgrade the SVG diagram with arrowed/selectable edges synchronized to selected calls.

**Tech Stack:** React 19, TypeScript, Vite, Vitest with jsdom, Testing Library, static JSON lifecycle manifests, SVG diagram rendering, Tailwind utility classes plus existing `index.css` component classes.

---

## File Structure

- Modify `explorer/src/lifecycle/types.ts`: add `LifecycleCall`, `LifecycleCallKind`, `LifecycleSelection`, and require `calls` on `LifecycleManifest`.
- Create `explorer/src/lifecycle/manifestValidation.ts`: validate lifecycle manifests and compute sorted calls.
- Create `explorer/src/lifecycle/manifestValidation.test.ts`: unit tests for required calls, broken refs, reverse response edges, and sorted call order.
- Modify `explorer/public/data/lifecycle/kilvin-asyncio-happy-path.json`: add ordered `calls` and any missing reverse/topology edges needed by the call model.
- Modify `explorer/src/lifecycle/LifecycleExplorer.test.tsx`: update fixture manifest with calls and assert the call sequence renders.
- Create `explorer/src/lifecycle/CallSequence.tsx`: render the numbered timeline and call selection buttons.
- Create `explorer/src/lifecycle/CallSequence.test.tsx`: component tests for phase highlighting and row selection.
- Modify `explorer/src/lifecycle/LifecycleDrawer.tsx`: support selected call details as well as selected node details.
- Modify `explorer/src/lifecycle/LifecycleDiagram.tsx`: add arrow markers, selected/active edge states, visible active labels, and edge pointer selection.
- Modify `explorer/src/lifecycle/LifecycleExplorer.tsx`: validate manifests, manage selected call/node union state, derive highlights from calls, wire timeline/diagram/drawer together.
- Modify `explorer/src/control/ControlPathsExplorer.test.tsx`: add `calls: []` or adjust lifecycle fixture to match the new required type only if production control-path loading needs the lifecycle type to compile.
- Modify `explorer/src/index.css`: add call sequence, selected call drawer, and upgraded diagram edge styles.

---

### Task 1: Add Lifecycle Call Types And Manifest Validation

**Files:**
- Modify: `explorer/src/lifecycle/types.ts`
- Create: `explorer/src/lifecycle/manifestValidation.ts`
- Create: `explorer/src/lifecycle/manifestValidation.test.ts`

- [ ] **Step 1: Add the failing validation tests**

Create `explorer/src/lifecycle/manifestValidation.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { getSortedLifecycleCalls, validateLifecycleManifest } from './manifestValidation'
import type { LifecycleManifest } from './types'

const baseManifest: LifecycleManifest = {
  generated_at: '2026-05-31T00:00:00Z',
  slug: 'test',
  label: 'Test manifest',
  phases: [
    {
      id: 'start',
      label: 'Start',
      summary: 'Start phase.',
      node_ids: ['app', 'server'],
      guide_anchor: 'start',
      guide_title: 'Start',
      hack_script: 'hacks/002_lifecycle_manifest.py',
      hack_summary: 'Run the lifecycle manifest hack.',
    },
  ],
  nodes: [
    {
      id: 'app',
      label: 'App',
      layer: 'kilvin',
      kind: 'client',
      summary: 'Starts work.',
      notes: 'Client code starts work.',
      refs: [],
    },
    {
      id: 'server',
      label: 'Server',
      layer: 'server',
      kind: 'service',
      summary: 'Accepts work.',
      notes: 'Server accepts work.',
      refs: [],
    },
  ],
  edges: [
    {
      id: 'app-server',
      from: 'app',
      to: 'server',
      kind: 'rpc',
      label: 'Start',
    },
  ],
  calls: [
    {
      id: 'start-rpc',
      phase_id: 'start',
      seq: 2,
      from: 'app',
      to: 'server',
      edge_id: 'app-server',
      kind: 'rpc',
      message: 'StartWorkflowExecution',
      summary: 'App starts a workflow.',
      details: ['The app sends a start request to the server frontend.'],
      refs: [],
    },
    {
      id: 'start-response',
      phase_id: 'start',
      seq: 1,
      from: 'server',
      to: 'app',
      edge_id: 'app-server',
      kind: 'response',
      message: 'Run id response',
      summary: 'Server returns the run id.',
      details: ['The response travels over the same topology edge in reverse.'],
      payload: ['run_id'],
      refs: [],
    },
  ],
}

describe('lifecycle manifest validation', () => {
  it('accepts a manifest with required calls and reverse response edges', () => {
    expect(() => validateLifecycleManifest(baseManifest)).not.toThrow()
  })

  it('sorts calls by global sequence number', () => {
    expect(getSortedLifecycleCalls(baseManifest).map((call) => call.id)).toEqual([
      'start-response',
      'start-rpc',
    ])
  })

  it('rejects manifests without calls', () => {
    const manifest = { ...baseManifest, calls: undefined } as unknown as LifecycleManifest

    expect(() => validateLifecycleManifest(manifest)).toThrow('Lifecycle manifest test must include calls')
  })

  it('rejects calls that reference missing nodes', () => {
    const manifest: LifecycleManifest = {
      ...baseManifest,
      calls: [
        {
          ...baseManifest.calls[0],
          to: 'missing-node',
        },
      ],
    }

    expect(() => validateLifecycleManifest(manifest)).toThrow(
      'Call start-rpc references missing to node missing-node',
    )
  })

  it('rejects calls whose edge does not connect the caller and callee', () => {
    const manifest: LifecycleManifest = {
      ...baseManifest,
      nodes: [
        ...baseManifest.nodes,
        {
          id: 'other',
          label: 'Other',
          layer: 'sdk-core',
          kind: 'worker',
          summary: 'Other node.',
          notes: 'Other node.',
          refs: [],
        },
      ],
      calls: [
        {
          ...baseManifest.calls[0],
          to: 'other',
        },
      ],
    }

    expect(() => validateLifecycleManifest(manifest)).toThrow(
      'Call start-rpc edge app-server does not connect app -> other',
    )
  })

  it('rejects duplicate sequence numbers', () => {
    const manifest: LifecycleManifest = {
      ...baseManifest,
      calls: [
        baseManifest.calls[0],
        {
          ...baseManifest.calls[1],
          seq: baseManifest.calls[0].seq,
        },
      ],
    }

    expect(() => validateLifecycleManifest(manifest)).toThrow('Duplicate lifecycle call seq 2')
  })
})
```

- [ ] **Step 2: Run the failing validation tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/manifestValidation.test.ts
```

Expected: FAIL because `manifestValidation.ts` does not exist and `LifecycleManifest` has no `calls` field.

- [ ] **Step 3: Add lifecycle call types**

Modify `explorer/src/lifecycle/types.ts`:

```ts
export type LayerId = 'kilvin' | 'sdk-python' | 'bridge' | 'sdk-core' | 'server'

export type LifecycleCallKind =
  | 'rpc'
  | 'poll'
  | 'response'
  | 'activation'
  | 'command'
  | 'completion'
  | 'heartbeat'
  | 'history-event'
  | 'task-dispatch'

export interface SourceRef {
  repo: string
  ref?: string
  label: string
  path: string
  line: number
  symbol: string
  url: string
}

export interface LifecycleNode {
  id: string
  label: string
  layer: LayerId
  kind: string
  summary: string
  notes: string
  refs: SourceRef[]
}

export interface LifecycleEdge {
  id: string
  from: string
  to: string
  kind: string
  label: string
}

export interface LifecycleCall {
  id: string
  phase_id: string
  seq: number
  from: string
  to: string
  edge_id: string
  kind: LifecycleCallKind
  message: string
  summary: string
  details: string[]
  payload?: string[]
  refs: SourceRef[]
}

export type LifecycleSelection =
  | { type: 'call'; call: LifecycleCall }
  | { type: 'node'; node: LifecycleNode }

export interface GuideHackLink {
  guide_anchor: string
  guide_title: string
  hack_script: string
  hack_summary: string
}

export interface LifecyclePhase extends GuideHackLink {
  id: string
  label: string
  summary: string
  node_ids: string[]
}

export interface LifecycleManifest {
  generated_at: string
  slug: string
  label: string
  phases: LifecyclePhase[]
  nodes: LifecycleNode[]
  edges: LifecycleEdge[]
  calls: LifecycleCall[]
}

export interface ControlScenario extends GuideHackLink {
  slug: string
  label: string
  summary: string
  details: string[]
  highlight_node_ids: string[]
  highlight_edge_ids: string[]
}
```

- [ ] **Step 4: Add manifest validation implementation**

Create `explorer/src/lifecycle/manifestValidation.ts`:

```ts
import type { LifecycleCall, LifecycleEdge, LifecycleManifest } from './types'

function requireText(value: string, message: string) {
  if (value.trim().length === 0) throw new Error(message)
}

function edgeConnects(edge: LifecycleEdge, from: string, to: string, kind: string): boolean {
  if (edge.from === from && edge.to === to) return true
  return kind === 'response' && edge.from === to && edge.to === from
}

export function getSortedLifecycleCalls(manifest: LifecycleManifest): LifecycleCall[] {
  validateLifecycleManifest(manifest)
  return [...manifest.calls].sort((a, b) => a.seq - b.seq)
}

export function validateLifecycleManifest(manifest: LifecycleManifest): void {
  if (!Array.isArray(manifest.calls) || manifest.calls.length === 0) {
    throw new Error(`Lifecycle manifest ${manifest.slug} must include calls`)
  }

  const phases = new Set(manifest.phases.map((phase) => phase.id))
  const nodes = new Set(manifest.nodes.map((node) => node.id))
  const edges = new Map(manifest.edges.map((edge) => [edge.id, edge]))
  const seqs = new Set<number>()
  const callCountByPhase = new Map(manifest.phases.map((phase) => [phase.id, 0]))

  for (const call of manifest.calls) {
    requireText(call.id, 'Lifecycle call id must not be empty')
    requireText(call.message, `Call ${call.id} must include message`)
    requireText(call.summary, `Call ${call.id} must include summary`)

    if (!Array.isArray(call.details) || call.details.length === 0) {
      throw new Error(`Call ${call.id} must include details`)
    }

    if (!phases.has(call.phase_id)) {
      throw new Error(`Call ${call.id} references missing phase ${call.phase_id}`)
    }

    if (!nodes.has(call.from)) {
      throw new Error(`Call ${call.id} references missing from node ${call.from}`)
    }

    if (!nodes.has(call.to)) {
      throw new Error(`Call ${call.id} references missing to node ${call.to}`)
    }

    const edge = edges.get(call.edge_id)
    if (!edge) {
      throw new Error(`Call ${call.id} references missing edge ${call.edge_id}`)
    }

    if (!edgeConnects(edge, call.from, call.to, call.kind)) {
      throw new Error(`Call ${call.id} edge ${call.edge_id} does not connect ${call.from} -> ${call.to}`)
    }

    if (seqs.has(call.seq)) {
      throw new Error(`Duplicate lifecycle call seq ${call.seq}`)
    }
    seqs.add(call.seq)

    callCountByPhase.set(call.phase_id, (callCountByPhase.get(call.phase_id) ?? 0) + 1)
  }

  for (const phase of manifest.phases) {
    if ((callCountByPhase.get(phase.id) ?? 0) === 0) {
      throw new Error(`Lifecycle phase ${phase.id} must include at least one call`)
    }
  }
}
```

- [ ] **Step 5: Run validation tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/manifestValidation.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add explorer/src/lifecycle/types.ts explorer/src/lifecycle/manifestValidation.ts explorer/src/lifecycle/manifestValidation.test.ts
git commit -m "Add lifecycle call manifest validation"
```

---

### Task 2: Migrate The Happy-Path Lifecycle Manifest To Ordered Calls

**Files:**
- Modify: `explorer/public/data/lifecycle/kilvin-asyncio-happy-path.json`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.test.tsx`
- Modify if typecheck requires it: `explorer/src/control/ControlPathsExplorer.test.tsx`

- [ ] **Step 1: Update the LifecycleExplorer fixture before production data**

Modify the `manifest` object in `explorer/src/lifecycle/LifecycleExplorer.test.tsx` so it includes a second node, one edge, and one call:

```ts
const manifest: LifecycleManifest = {
  generated_at: '2026-05-31T00:00:00Z',
  slug: 'kilvin-asyncio-happy-path',
  label: 'Kilvin asyncio happy path',
  phases: [
    {
      id: 'start',
      label: 'Start workflow',
      summary: 'Kilvin submits a staged training run.',
      node_ids: ['kilvin-client', 'frontend-service'],
      guide_anchor: 'happy-path-start-workflow-to-first-activation',
      guide_title: '4. Happy path: start workflow to first activation',
      hack_script: 'hacks/002_lifecycle_manifest.py',
      hack_summary: 'Walk the Kilvin asyncio happy-path lifecycle manifest in phase order.',
    },
  ],
  nodes: [
    {
      id: 'kilvin-client',
      label: 'Kilvin client',
      layer: 'kilvin',
      kind: 'client',
      summary: 'Starts the workflow.',
      notes: 'Client start crosses Frontend.',
      refs: [],
    },
    {
      id: 'frontend-service',
      label: 'Frontend',
      layer: 'server',
      kind: 'service',
      summary: 'Accepts workflow starts.',
      notes: 'Frontend accepts public workflow RPCs.',
      refs: [],
    },
  ],
  edges: [
    {
      id: 'start-rpc',
      from: 'kilvin-client',
      to: 'frontend-service',
      kind: 'rpc',
      label: 'StartWorkflowExecution',
    },
  ],
  calls: [
    {
      id: 'call-start-workflow',
      phase_id: 'start',
      seq: 1,
      from: 'kilvin-client',
      to: 'frontend-service',
      edge_id: 'start-rpc',
      kind: 'rpc',
      message: 'StartWorkflowExecution',
      summary: 'Kilvin asks Temporal to start the command workflow.',
      details: ['The app submits workflow id, task queue, workflow type, and staged training input.'],
      payload: ['workflow_id', 'task_queue', 'workflow_type', 'input'],
      refs: [],
    },
  ],
}
```

- [ ] **Step 2: Run tests to expose missing call UI wiring**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: PASS or FAIL only because later tasks have not rendered the call sequence. Type errors about missing `calls` in fixtures must be fixed in this task.

- [ ] **Step 3: Add `calls` to the production JSON**

Modify `explorer/public/data/lifecycle/kilvin-asyncio-happy-path.json` by adding a top-level `calls` array after `edges`. Use these exact call objects, adapting only comma placement to valid JSON:

```json
"calls": [
  {
    "id": "call-start-workflow",
    "phase_id": "start",
    "seq": 1,
    "from": "kilvin-client",
    "to": "frontend-service",
    "edge_id": "start-rpc",
    "kind": "rpc",
    "message": "StartWorkflowExecution",
    "summary": "Kilvin asks Temporal Frontend to start the command workflow.",
    "details": [
      "The client sends workflow id, task queue, workflow type, and staged training input.",
      "Frontend is the public gRPC boundary; it accepts the request before History records durable state."
    ],
    "payload": ["workflow_id", "task_queue", "workflow_type", "staged training config"],
    "refs": []
  },
  {
    "id": "call-record-start",
    "phase_id": "start",
    "seq": 2,
    "from": "frontend-service",
    "to": "history-service",
    "edge_id": "history-start",
    "kind": "history-event",
    "message": "WorkflowExecutionStarted",
    "summary": "Frontend routes the start to History so the workflow has durable event state.",
    "details": [
      "History owns the event log that workflow replay will later consume.",
      "The start request becomes durable history before workers execute user workflow code."
    ],
    "payload": ["WorkflowExecutionStarted event", "run id", "workflow task schedule attributes"],
    "refs": []
  },
  {
    "id": "call-enqueue-first-workflow-task",
    "phase_id": "start",
    "seq": 3,
    "from": "history-service",
    "to": "matching-service",
    "edge_id": "schedule-wft",
    "kind": "task-dispatch",
    "message": "workflow task",
    "summary": "History asks Matching to make the first workflow task available on the task queue.",
    "details": [
      "The server does not directly invoke the worker process.",
      "Matching holds task queue work until an SDK worker poll is available."
    ],
    "payload": ["task queue", "workflow task token"],
    "refs": []
  },
  {
    "id": "call-python-poll-activation",
    "phase_id": "poll",
    "seq": 4,
    "from": "python-worker",
    "to": "bridge-worker",
    "edge_id": "worker-poll",
    "kind": "poll",
    "message": "poll_workflow_activation",
    "summary": "Python Worker.run awaits the next workflow activation through the bridge.",
    "details": [
      "Python owns asyncio worker orchestration and user-code execution.",
      "The bridge call crosses from Python into the Rust core worker."
    ],
    "payload": ["task queue", "worker identity"],
    "refs": []
  },
  {
    "id": "call-bridge-core-poll",
    "phase_id": "poll",
    "seq": 5,
    "from": "bridge-worker",
    "to": "core-worker",
    "edge_id": "bridge-core",
    "kind": "poll",
    "message": "core poller request",
    "summary": "The bridge forwards Python's poll request into sdk-core.",
    "details": [
      "The C bridge serializes Python calls into core worker operations.",
      "sdk-core manages pollers, task slots, workflow cache, and server calls."
    ],
    "payload": ["poll_workflow_activation request"],
    "refs": []
  },
  {
    "id": "call-core-poll-matching",
    "phase_id": "poll",
    "seq": 6,
    "from": "core-worker",
    "to": "matching-service",
    "edge_id": "core-matching",
    "kind": "poll",
    "message": "PollWorkflowTaskQueue",
    "summary": "sdk-core long-polls Matching for workflow work.",
    "details": [
      "This direction is important: the worker calls the server.",
      "Matching can only return a task because a poll is already open."
    ],
    "payload": ["namespace", "task queue", "worker identity"],
    "refs": []
  },
  {
    "id": "call-matching-workflow-task",
    "phase_id": "poll",
    "seq": 7,
    "from": "matching-service",
    "to": "core-worker",
    "edge_id": "core-matching",
    "kind": "response",
    "message": "workflow task response",
    "summary": "Matching returns the queued workflow task to sdk-core.",
    "details": [
      "This is the response to the long poll, not a server push.",
      "The response contains enough task data for core to build a workflow activation."
    ],
    "payload": ["workflow task token", "history events"],
    "refs": []
  },
  {
    "id": "call-core-activation",
    "phase_id": "activate",
    "seq": 8,
    "from": "core-worker",
    "to": "workflow-activation",
    "edge_id": "activation-up",
    "kind": "activation",
    "message": "WorkflowActivation",
    "summary": "sdk-core turns the workflow task into a Python workflow activation.",
    "details": [
      "Core applies workflow state machines and cache rules before handing work to Python.",
      "Python receives deterministic activation jobs and resumes workflow code."
    ],
    "payload": ["activation jobs", "history slice", "run id"],
    "refs": []
  },
  {
    "id": "call-schedule-activity-command",
    "phase_id": "schedule-activity",
    "seq": 9,
    "from": "workflow-activation",
    "to": "history-service",
    "edge_id": "activity-command",
    "kind": "command",
    "message": "ScheduleActivityTask command",
    "summary": "Workflow code emits a command that asks History to schedule an activity.",
    "details": [
      "Workflow code does not run side effects directly.",
      "The command is recorded through workflow task completion and interpreted by History."
    ],
    "payload": ["activity type", "activity id", "task queue", "timeouts"],
    "refs": []
  },
  {
    "id": "call-enqueue-activity-task",
    "phase_id": "schedule-activity",
    "seq": 10,
    "from": "history-service",
    "to": "matching-service",
    "edge_id": "activity-dispatch",
    "kind": "task-dispatch",
    "message": "activity task",
    "summary": "History enqueues the activity task for a polling worker.",
    "details": [
      "Matching again mediates delivery through task queue polling.",
      "The activity will run only when an SDK worker polls for it."
    ],
    "payload": ["activity task token", "task queue"],
    "refs": []
  },
  {
    "id": "call-core-activity-task",
    "phase_id": "execute-activity",
    "seq": 11,
    "from": "core-worker",
    "to": "activity-task",
    "edge_id": "activity-poll",
    "kind": "activation",
    "message": "ActivityTask",
    "summary": "sdk-core delivers the activity task to Python activity execution.",
    "details": [
      "Python activity code can perform side effects such as allocation, materialization, and monitoring.",
      "Activity execution is not replayed as deterministic workflow code."
    ],
    "payload": ["activity input", "heartbeat details", "task token"],
    "refs": []
  },
  {
    "id": "call-activity-heartbeat",
    "phase_id": "execute-activity",
    "seq": 12,
    "from": "activity-task",
    "to": "core-worker",
    "edge_id": "heartbeat",
    "kind": "heartbeat",
    "message": "RecordHeartbeat",
    "summary": "Python activity code reports progress through sdk-core.",
    "details": [
      "Heartbeats let the server observe progress and deliver cancellation.",
      "sdk-core batches and forwards heartbeat information to the server boundary."
    ],
    "payload": ["progress details", "task token"],
    "refs": []
  },
  {
    "id": "call-activity-complete",
    "phase_id": "execute-activity",
    "seq": 13,
    "from": "activity-task",
    "to": "history-service",
    "edge_id": "activity-complete",
    "kind": "completion",
    "message": "ActivityTaskCompleted",
    "summary": "The activity result is recorded back into workflow history.",
    "details": [
      "Completion makes the activity result durable.",
      "History can then schedule another workflow task so workflow code can observe the result."
    ],
    "payload": ["activity result", "ActivityTaskCompleted event"],
    "refs": []
  },
  {
    "id": "call-workflow-task-complete",
    "phase_id": "complete",
    "seq": 14,
    "from": "workflow-activation",
    "to": "history-service",
    "edge_id": "workflow-complete",
    "kind": "completion",
    "message": "RespondWorkflowTaskCompleted",
    "summary": "Python workflow completion data is applied to durable workflow history.",
    "details": [
      "Workflow task completion carries commands produced by deterministic workflow code.",
      "History appends events and may schedule the next workflow task."
    ],
    "payload": ["workflow commands", "new history events"],
    "refs": []
  },
  {
    "id": "call-enqueue-followup-workflow-task",
    "phase_id": "complete",
    "seq": 15,
    "from": "history-service",
    "to": "matching-service",
    "edge_id": "schedule-wft",
    "kind": "task-dispatch",
    "message": "follow-up workflow task",
    "summary": "History asks Matching to make the next workflow task available.",
    "details": [
      "Follow-up workflow tasks let workflow code observe activity results and continue.",
      "The next turn still arrives through worker polling."
    ],
    "payload": ["task queue", "workflow task token"],
    "refs": []
  }
]
```

- [ ] **Step 4: Run typecheck and lifecycle tests**

Run:

```bash
cd explorer && npm run typecheck && npm test -- --run src/lifecycle/manifestValidation.test.ts src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: PASS. If `ControlPathsExplorer.test.tsx` fails to typecheck because `LifecycleManifest` now requires `calls`, add `calls: []` to the test fixture only when the production control-path code does not validate that fixture as a lifecycle page manifest.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add explorer/public/data/lifecycle/kilvin-asyncio-happy-path.json explorer/src/lifecycle/LifecycleExplorer.test.tsx explorer/src/control/ControlPathsExplorer.test.tsx
git commit -m "Add ordered calls to lifecycle manifest"
```

---

### Task 3: Build The Call Sequence Timeline Component

**Files:**
- Create: `explorer/src/lifecycle/CallSequence.tsx`
- Create: `explorer/src/lifecycle/CallSequence.test.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add failing CallSequence component tests**

Create `explorer/src/lifecycle/CallSequence.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import CallSequence from './CallSequence'
import type { LifecycleCall } from './types'

const calls: LifecycleCall[] = [
  {
    id: 'call-start',
    phase_id: 'start',
    seq: 1,
    from: 'kilvin-client',
    to: 'frontend-service',
    edge_id: 'start-rpc',
    kind: 'rpc',
    message: 'StartWorkflowExecution',
    summary: 'Kilvin asks Temporal to start a workflow.',
    details: ['The client sends a start request.'],
    payload: ['workflow_id'],
    refs: [],
  },
  {
    id: 'call-poll',
    phase_id: 'poll',
    seq: 2,
    from: 'core-worker',
    to: 'matching-service',
    edge_id: 'core-matching',
    kind: 'poll',
    message: 'PollWorkflowTaskQueue',
    summary: 'Core long-polls Matching.',
    details: ['The worker calls the server.'],
    refs: [],
  },
]

const labels = new Map([
  ['kilvin-client', 'Kilvin client'],
  ['frontend-service', 'Frontend'],
  ['core-worker', 'Core worker'],
  ['matching-service', 'Matching'],
])

describe('CallSequence', () => {
  it('renders ordered call rows with endpoint labels and messages', () => {
    render(
      <CallSequence
        calls={calls}
        nodeLabels={labels}
        activePhaseId="start"
        selectedCallId="call-start"
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /01 Kilvin client to Frontend StartWorkflowExecution/ })).toBeTruthy()
    expect(screen.getByText('Kilvin asks Temporal to start a workflow.')).toBeTruthy()
    expect(screen.getByText('Core long-polls Matching.')).toBeTruthy()
  })

  it('marks selected and active phase rows', () => {
    render(
      <CallSequence
        calls={calls}
        nodeLabels={labels}
        activePhaseId="start"
        selectedCallId="call-start"
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /01 Kilvin client/ }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: /02 Core worker/ }).getAttribute('data-active-phase')).toBe('false')
  })

  it('selects a row', () => {
    const onSelect = vi.fn()

    render(
      <CallSequence
        calls={calls}
        nodeLabels={labels}
        activePhaseId="start"
        selectedCallId="call-start"
        onSelect={onSelect}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /02 Core worker/ }))

    expect(onSelect).toHaveBeenCalledWith(calls[1])
  })
})
```

- [ ] **Step 2: Run the failing CallSequence tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/CallSequence.test.tsx
```

Expected: FAIL because `CallSequence.tsx` does not exist.

- [ ] **Step 3: Implement CallSequence**

Create `explorer/src/lifecycle/CallSequence.tsx`:

```tsx
import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LifecycleCall } from './types'

function formatSeq(seq: number): string {
  return seq.toString().padStart(2, '0')
}

export default function CallSequence({
  calls,
  nodeLabels,
  activePhaseId,
  selectedCallId,
  onSelect,
}: {
  calls: LifecycleCall[]
  nodeLabels: Map<string, string>
  activePhaseId: string
  selectedCallId: string | null
  onSelect: (call: LifecycleCall) => void
}) {
  return (
    <section className="call-sequence" aria-label="Lifecycle call sequence">
      <div className="call-sequence-header">
        <h3>Call Sequence</h3>
        <span>{calls.length} calls</span>
      </div>
      <div className="call-sequence-list">
        {calls.map((call) => {
          const from = nodeLabels.get(call.from) ?? call.from
          const to = nodeLabels.get(call.to) ?? call.to
          const selected = selectedCallId === call.id
          const activePhase = call.phase_id === activePhaseId

          return (
            <button
              key={call.id}
              type="button"
              className={cn('call-sequence-row', selected && 'selected', activePhase && 'active-phase')}
              aria-pressed={selected}
              data-active-phase={String(activePhase)}
              onClick={() => onSelect(call)}
            >
              <span className="call-sequence-seq">{formatSeq(call.seq)}</span>
              <span className="call-sequence-body">
                <span className="call-sequence-route">
                  <span>{from}</span>
                  <ArrowRight size={13} aria-hidden="true" />
                  <span>{to}</span>
                </span>
                <span className="call-sequence-message">{call.message}</span>
                <span className="call-sequence-summary">{call.summary}</span>
              </span>
              <span className={cn('call-sequence-kind', `kind-${call.kind}`)}>{call.kind}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Add CallSequence styles**

Append near the lifecycle styles in `explorer/src/index.css`:

```css
.call-sequence {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.call-sequence-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.call-sequence-header h3 {
  margin: 0;
  color: var(--color-ink);
  font-size: 15px;
  font-weight: 700;
}

.call-sequence-header span {
  color: var(--color-ink-muted);
  font-family: var(--font-mono);
  font-size: 11px;
}

.call-sequence-list {
  display: grid;
  gap: 8px;
}

.call-sequence-row {
  appearance: none;
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
  padding: 10px;
  border: 1px solid var(--color-panelborder);
  border-radius: var(--radius-btn);
  background: rgba(15, 23, 42, 0.36);
  color: inherit;
  cursor: pointer;
  text-align: left;
  opacity: 0.58;
}

.call-sequence-row.active-phase,
.call-sequence-row.selected {
  opacity: 1;
}

.call-sequence-row.selected {
  border-color: var(--color-cyan);
  background: rgba(6, 182, 212, 0.1);
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.12);
}

.call-sequence-row:focus-visible {
  outline: 2px solid var(--color-cyan);
  outline-offset: 2px;
}

.call-sequence-seq {
  color: var(--color-cyan);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

.call-sequence-body {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.call-sequence-route {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  color: var(--color-ink);
  font-size: 12px;
  font-weight: 700;
}

.call-sequence-message {
  color: var(--color-ink);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.call-sequence-summary {
  color: var(--color-ink-soft);
  font-size: 12px;
  line-height: 1.45;
}

.call-sequence-kind {
  max-width: 96px;
  overflow-wrap: anywhere;
  border: 1px solid var(--color-panelborder);
  border-radius: var(--radius-badge);
  padding: 3px 6px;
  color: var(--color-ink-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  text-transform: uppercase;
}
```

- [ ] **Step 5: Run CallSequence tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/CallSequence.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add explorer/src/lifecycle/CallSequence.tsx explorer/src/lifecycle/CallSequence.test.tsx explorer/src/index.css
git commit -m "Add lifecycle call sequence component"
```

---

### Task 4: Add Call Details To The Lifecycle Drawer

**Files:**
- Modify: `explorer/src/lifecycle/LifecycleDrawer.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.test.tsx`

- [ ] **Step 1: Add a failing drawer assertion to LifecycleExplorer test**

Add these assertions to `renders phase guide and hack links` after the existing `waitFor` block in `explorer/src/lifecycle/LifecycleExplorer.test.tsx`:

```ts
expect(screen.getByText('StartWorkflowExecution')).toBeTruthy()
expect(screen.getByText('Kilvin asks Temporal to start the command workflow.')).toBeTruthy()
expect(screen.getByText('workflow_id')).toBeTruthy()
```

- [ ] **Step 2: Run the failing lifecycle test**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: FAIL because the explorer does not select or render call details yet.

- [ ] **Step 3: Update LifecycleDrawer to support call selections**

Replace the current `LifecycleDrawer` props and body in `explorer/src/lifecycle/LifecycleDrawer.tsx` with this implementation, keeping the existing imports and `GuideHackPanel` helper:

```tsx
import { ArrowRight, BookOpen, ExternalLink, Terminal } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { guideUrl } from '@/lib/assets'
import type { LifecycleCall, LifecycleNode, LifecyclePhase, LifecycleSelection } from './types'

function GuideHackPanel({ phase }: { phase: LifecyclePhase | null }) {
  if (!phase) return null

  return (
    <div className="guide-hack-panel">
      <h4 className="font-mono text-xs uppercase text-ink-muted">Read / Run / Inspect</h4>
      <a className="guide-action" href={guideUrl(phase.guide_anchor)} target="_blank" rel="noopener noreferrer">
        <BookOpen size={13} aria-hidden="true" />
        <span>{phase.guide_title}</span>
      </a>
      <div className="guide-command">
        <Terminal size={13} aria-hidden="true" />
        <code>python {phase.hack_script}</code>
      </div>
      <p className="text-xs text-ink-soft">{phase.hack_summary}</p>
    </div>
  )
}

function SourceRefs({ refs }: { refs: LifecycleNode['refs'] }) {
  if (refs.length === 0) return null

  return (
    <div>
      <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Source refs</h4>
      <div className="space-y-2">
        {refs.map((ref) => (
          <a
            key={`${ref.repo}:${ref.path}:${ref.line}`}
            className="source-link"
            href={`${ref.url}#L${ref.line}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className="source-link-label">{ref.label}</span>
            <span className="source-link-path font-mono text-[11px] text-ink-muted">
              {ref.path}:{ref.line}
            </span>
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        ))}
      </div>
    </div>
  )
}

function CallDetails({
  call,
  phase,
  nodeLabels,
}: {
  call: LifecycleCall
  phase: LifecyclePhase | null
  nodeLabels: Map<string, string>
}) {
  const from = nodeLabels.get(call.from) ?? call.from
  const to = nodeLabels.get(call.to) ?? call.to

  return (
    <Card>
      <CardHeader>
        <CardTitle>{call.message}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {from} <ArrowRight size={12} aria-hidden="true" className="inline" /> {to}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="call-detail-meta">
          <span>{call.kind}</span>
          <span>{phase?.label ?? call.phase_id}</span>
        </div>
        <p className="text-ink">{call.summary}</p>
        <ul className="call-detail-list">
          {call.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
        {call.payload && call.payload.length > 0 ? (
          <div>
            <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Payload</h4>
            <div className="call-payload-list">
              {call.payload.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </div>
        ) : null}
        <GuideHackPanel phase={phase} />
        <SourceRefs refs={call.refs} />
      </CardContent>
    </Card>
  )
}

export default function LifecycleDrawer({
  selection,
  phase,
  nodeLabels,
}: {
  selection: LifecycleSelection | null
  phase: LifecyclePhase | null
  nodeLabels: Map<string, string>
}) {
  if (selection?.type === 'call') {
    return <CallDetails call={selection.call} phase={phase} nodeLabels={nodeLabels} />
  }

  if (!selection) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{phase?.label ?? 'Select a call'}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-ink-soft">
          <div className="space-y-4">
            <p>{phase?.summary ?? 'Choose a lifecycle call or node to inspect source-backed details.'}</p>
            <p>Read the ordered call sequence, then inspect a call for boundary and payload details.</p>
            <GuideHackPanel phase={phase} />
          </div>
        </CardContent>
      </Card>
    )
  }

  const node = selection.node

  return (
    <Card>
      <CardHeader>
        <CardTitle>{node.label}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {node.layer} · {node.kind}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-ink">{node.summary}</p>
        <p className="text-ink-soft">{node.notes}</p>
        <GuideHackPanel phase={phase} />
        <SourceRefs refs={node.refs} />
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 4: Add drawer styles**

Append near the lifecycle styles in `explorer/src/index.css`:

```css
.call-detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.call-detail-meta span,
.call-payload-list span {
  border: 1px solid var(--color-panelborder);
  border-radius: var(--radius-badge);
  padding: 4px 7px;
  color: var(--color-ink-soft);
  font-family: var(--font-mono);
  font-size: 11px;
}

.call-detail-list {
  margin: 0;
  padding-left: 18px;
  color: var(--color-ink-soft);
}

.call-detail-list li + li {
  margin-top: 6px;
}

.call-payload-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
```

- [ ] **Step 5: Run the lifecycle test**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: still FAIL until Task 6 wires selected calls into the drawer, or PASS if Task 6 is completed in the same execution batch.

- [ ] **Step 6: Commit Task 4 after the drawer is wired by Task 6**

Run this commit only after tests pass:

```bash
git add explorer/src/lifecycle/LifecycleDrawer.tsx explorer/src/lifecycle/LifecycleExplorer.test.tsx explorer/src/index.css
git commit -m "Show lifecycle call details in drawer"
```

---

### Task 5: Upgrade The Lifecycle Diagram For Directed Selectable Edges

**Files:**
- Modify: `explorer/src/lifecycle/LifecycleDiagram.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Update LifecycleDiagram props and edge behavior**

Modify `explorer/src/lifecycle/LifecycleDiagram.tsx` to accept selected edge and edge selection props:

```tsx
import { cn } from '@/lib/utils'
import type { LifecycleEdge, LifecycleNode } from './types'

const LAYERS = [
  { id: 'kilvin', label: 'Kilvin app', y: 34 },
  { id: 'sdk-python', label: 'Python SDK', y: 134 },
  { id: 'bridge', label: 'Bridge', y: 234 },
  { id: 'sdk-core', label: 'sdk-core', y: 334 },
  { id: 'server', label: 'Temporal server', y: 434 },
] as const

const X: Record<string, number> = {
  'kilvin-client': 70,
  'python-worker': 70,
  'bridge-worker': 250,
  'core-runtime': 70,
  'core-worker': 250,
  'frontend-service': 70,
  'history-service': 250,
  'matching-service': 430,
  'workflow-activation': 430,
  'activity-task': 610,
}

function nodeWidth(label: string): number {
  return Math.max(132, label.length * 8.2 + 38)
}

function nodeBox(node: LifecycleNode) {
  const layer = LAYERS.find((item) => item.id === node.layer) ?? LAYERS[0]
  const x = X[node.id] ?? 70
  const width = nodeWidth(node.label)

  return {
    x,
    y: layer.y + 24,
    width,
    height: 50,
    cx: x + width / 2,
    cy: layer.y + 49,
  }
}

export default function LifecycleDiagram({
  nodes,
  edges,
  activeNodeIds,
  activeEdgeIds,
  selectedNodeIds,
  selectedEdgeId,
  selectedNodeId,
  onSelectNode,
  onSelectEdge,
}: {
  nodes: LifecycleNode[]
  edges: LifecycleEdge[]
  activeNodeIds: Set<string>
  activeEdgeIds: Set<string>
  selectedNodeIds: Set<string>
  selectedEdgeId: string | null
  selectedNodeId: string | null
  onSelectNode: (node: LifecycleNode) => void
  onSelectEdge: (edge: LifecycleEdge) => void
}) {
  const byId = new Map(nodes.map((node) => [node.id, node]))

  return (
    <svg viewBox="0 0 820 560" className="lifecycle-svg" role="group" aria-label="Temporal lifecycle diagram">
      <defs>
        <marker
          id="lifecycle-arrow"
          markerWidth="8"
          markerHeight="8"
          refX="7"
          refY="4"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L8,4 L0,8 z" className="lifecycle-arrow-marker" />
        </marker>
      </defs>

      {LAYERS.map((layer) => (
        <g key={layer.id}>
          <rect className="lifecycle-lane" x={12} y={layer.y} width={796} height={92} rx={12} />
          <text className="lifecycle-lane-label" x={26} y={layer.y + 22}>
            {layer.label}
          </text>
        </g>
      ))}

      {edges.map((edge) => {
        const from = byId.get(edge.from)
        const to = byId.get(edge.to)

        if (!from || !to) return null

        const a = nodeBox(from)
        const b = nodeBox(to)
        const active = activeEdgeIds.has(edge.id)
        const selected = selectedEdgeId === edge.id
        const labelX = (a.cx + b.cx) / 2
        const labelY = (a.cy + b.cy) / 2 - 7

        return (
          <g key={edge.id} className={cn('lifecycle-edge', active && 'active', selected && 'selected')}>
            <line
              x1={a.cx}
              y1={a.cy}
              x2={b.cx}
              y2={b.cy}
              markerEnd="url(#lifecycle-arrow)"
              role="button"
              aria-label={edge.label}
              onClick={() => onSelectEdge(edge)}
            />
            {(active || selected) && (
              <text className="lifecycle-edge-label" x={labelX} y={labelY} textAnchor="middle">
                {edge.label}
              </text>
            )}
            <title>{edge.label}</title>
          </g>
        )
      })}

      {nodes.map((node) => {
        const box = nodeBox(node)
        const active = activeNodeIds.has(node.id)
        const selected = selectedNodeId === node.id || selectedNodeIds.has(node.id)

        return (
          <g
            key={node.id}
            className={cn('lifecycle-node', active && 'active', selected && 'selected')}
            transform={`translate(${box.x},${box.y})`}
            role="button"
            tabIndex={0}
            aria-label={node.label}
            onClick={() => onSelectNode(node)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onSelectNode(node)
              }
            }}
          >
            <rect width={box.width} height={box.height} rx={8} />
            <text x={box.width / 2} y={30} textAnchor="middle">
              {node.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
```

- [ ] **Step 2: Update diagram styles**

Modify lifecycle edge styles in `explorer/src/index.css`:

```css
.lifecycle-arrow-marker {
  fill: rgba(148, 163, 184, 0.45);
}

.lifecycle-edge line {
  stroke: rgba(148, 163, 184, 0.32);
  stroke-width: 1.4;
  cursor: pointer;
}

.lifecycle-edge.active line {
  stroke: var(--color-cyan);
  stroke-width: 2.2;
  filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.35));
}

.lifecycle-edge.selected line {
  stroke: var(--color-warning);
  stroke-width: 3;
  filter: drop-shadow(0 0 8px rgba(245, 158, 11, 0.45));
}

.lifecycle-edge.active .lifecycle-arrow-marker,
.lifecycle-edge.selected .lifecycle-arrow-marker {
  fill: currentColor;
}

.lifecycle-edge-label {
  paint-order: stroke;
  stroke: rgba(7, 10, 19, 0.92);
  stroke-width: 4px;
  fill: var(--color-ink);
  font-size: 10px;
  font-weight: 600;
  pointer-events: none;
}
```

- [ ] **Step 3: Run lifecycle tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: FAIL until Task 6 updates `LifecycleExplorer` to pass the new diagram props.

- [ ] **Step 4: Commit Task 5 after Task 6 wiring passes tests**

Run this commit only after `LifecycleExplorer` is updated:

```bash
git add explorer/src/lifecycle/LifecycleDiagram.tsx explorer/src/index.css
git commit -m "Add directed lifecycle diagram edges"
```

---

### Task 6: Wire Calls Through LifecycleExplorer

**Files:**
- Modify: `explorer/src/lifecycle/LifecycleExplorer.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.test.tsx`

- [ ] **Step 1: Add integration assertions for the call sequence**

Extend `explorer/src/lifecycle/LifecycleExplorer.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
```

Add this test:

```tsx
it('selects call rows and updates call details', async () => {
  render(<LifecycleExplorer navigate={vi.fn()} />)

  await waitFor(() => {
    expect(screen.getByRole('button', { name: /01 Kilvin client to Frontend StartWorkflowExecution/ })).toBeTruthy()
  })

  fireEvent.click(screen.getByRole('button', { name: /01 Kilvin client to Frontend StartWorkflowExecution/ }))

  expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()
  expect(screen.getByText('workflow_id')).toBeTruthy()
})
```

- [ ] **Step 2: Run the failing integration test**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: FAIL because `LifecycleExplorer` has not rendered `CallSequence` or passed call selections to the drawer.

- [ ] **Step 3: Wire validation, sorted calls, selection, and highlights**

Modify `explorer/src/lifecycle/LifecycleExplorer.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { ViewTabs } from '@/explorer-kit/ViewTabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import CallSequence from './CallSequence'
import LifecycleDiagram from './LifecycleDiagram'
import LifecycleDrawer from './LifecycleDrawer'
import { getSortedLifecycleCalls, validateLifecycleManifest } from './manifestValidation'
import type { LifecycleCall, LifecycleEdge, LifecycleManifest, LifecycleNode, LifecycleSelection } from './types'

interface LifecycleEntry {
  slug: string
  label: string
  manifest: string
}

function selectCallForEdge(calls: LifecycleCall[], edge: LifecycleEdge, activePhaseId: string): LifecycleCall | null {
  return (
    calls.find((call) => call.phase_id === activePhaseId && call.edge_id === edge.id) ??
    calls.find((call) => call.edge_id === edge.id) ??
    null
  )
}

export default function LifecycleExplorer(_props: ExplorerModeProps) {
  const [index, setIndex] = useState<LifecycleEntry[] | null>(null)
  const [indexError, setIndexError] = useState<string | null>(null)
  const [slug, setSlug] = useState<string>('')
  const [manifest, setManifest] = useState<LifecycleManifest | null>(null)
  const [manifestError, setManifestError] = useState<string | null>(null)
  const [phaseId, setPhaseId] = useState<string>('')
  const [selection, setSelection] = useState<LifecycleSelection | null>(null)

  useEffect(() => {
    fetchExplorerJson<LifecycleEntry[]>('lifecycle/index.json')
      .then((entries) => {
        setIndex(entries)
        setSlug(entries[0]?.slug ?? '')
      })
      .catch((error: unknown) => setIndexError(errorMessage(error)))
  }, [])

  const entry = index?.find((item) => item.slug === slug) ?? null

  useEffect(() => {
    if (!entry) return

    let isCurrent = true

    fetchExplorerJson<LifecycleManifest>(entry.manifest)
      .then((loaded) => {
        if (!isCurrent) return

        validateLifecycleManifest(loaded)
        const sortedCalls = getSortedLifecycleCalls(loaded)

        setManifest(loaded)
        setPhaseId(loaded.phases[0]?.id ?? '')
        setSelection(sortedCalls[0] ? { type: 'call', call: sortedCalls[0] } : null)
      })
      .catch((error: unknown) => {
        if (!isCurrent) return

        setManifestError(errorMessage(error))
      })

    return () => {
      isCurrent = false
    }
  }, [entry])

  function handleSlugChange(nextSlug: string) {
    setSlug(nextSlug)
    setManifest(null)
    setManifestError(null)
    setSelection(null)
  }

  const phase = manifest?.phases.find((item) => item.id === phaseId) ?? manifest?.phases[0] ?? null
  const calls = useMemo(() => (manifest ? getSortedLifecycleCalls(manifest) : []), [manifest])
  const nodeLabels = useMemo(() => new Map(manifest?.nodes.map((node) => [node.id, node.label]) ?? []), [manifest])
  const selectedCall = selection?.type === 'call' ? selection.call : null
  const selectedNode = selection?.type === 'node' ? selection.node : null

  const activePhaseCalls = useMemo(
    () => calls.filter((call) => call.phase_id === (phase?.id ?? '')),
    [calls, phase],
  )

  const activeNodeIds = useMemo(() => {
    const ids = new Set<string>()
    for (const call of activePhaseCalls) {
      ids.add(call.from)
      ids.add(call.to)
    }
    return ids
  }, [activePhaseCalls])

  const activeEdgeIds = useMemo(
    () => new Set(activePhaseCalls.map((call) => call.edge_id)),
    [activePhaseCalls],
  )

  const selectedNodeIds = useMemo(() => {
    if (!selectedCall) return new Set<string>()
    return new Set([selectedCall.from, selectedCall.to])
  }, [selectedCall])

  if (!index) {
    return (
      <AsyncBoundary
        loading={indexError === null}
        error={indexError}
        loadingLabel="Loading lifecycle index..."
        errorPrefix="Failed to load lifecycle index"
      />
    )
  }

  if (!manifest) {
    return (
      <AsyncBoundary
        loading={manifestError === null}
        error={manifestError}
        loadingLabel="Loading lifecycle manifest..."
        errorPrefix="Failed to load lifecycle manifest"
      />
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <SubjectSwitcher
          label="Lifecycle"
          ariaLabel="Lifecycle subject"
          value={slug}
          options={index.map((item) => ({ value: item.slug, label: item.label }))}
          onChange={handleSlugChange}
        />
        <ViewTabs
          ariaLabel="Lifecycle phase"
          value={phase?.id ?? ''}
          onChange={setPhaseId}
          options={manifest.phases.map((item) => ({ value: item.id, label: item.label }))}
        />
      </div>
      <div className="lifecycle-workspace">
        <div className="lifecycle-primary">
          <Card>
            <CardHeader>
              <CardTitle>{phase?.label ?? manifest.label}</CardTitle>
              <p className="text-sm text-ink-soft">{phase?.summary}</p>
            </CardHeader>
            <CardContent>
              <LifecycleDiagram
                nodes={manifest.nodes}
                edges={manifest.edges}
                activeNodeIds={activeNodeIds}
                activeEdgeIds={activeEdgeIds}
                selectedNodeIds={selectedNodeIds}
                selectedEdgeId={selectedCall?.edge_id ?? null}
                selectedNodeId={selectedNode?.id ?? null}
                onSelectNode={(node: LifecycleNode) => setSelection({ type: 'node', node })}
                onSelectEdge={(edge: LifecycleEdge) => {
                  const call = selectCallForEdge(calls, edge, phase?.id ?? '')
                  if (call) setSelection({ type: 'call', call })
                }}
              />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <CallSequence
                calls={calls}
                nodeLabels={nodeLabels}
                activePhaseId={phase?.id ?? ''}
                selectedCallId={selectedCall?.id ?? null}
                onSelect={(call) => setSelection({ type: 'call', call })}
              />
            </CardContent>
          </Card>
        </div>
        <div className="xl:sticky xl:top-6">
          <LifecycleDrawer selection={selection} phase={phase} nodeLabels={nodeLabels} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Add workspace layout styles**

Add to `explorer/src/index.css` near lifecycle styles:

```css
.lifecycle-workspace {
  display: grid;
  gap: 20px;
  align-items: start;
}

.lifecycle-primary {
  display: grid;
  gap: 20px;
}

@media (min-width: 1280px) {
  .lifecycle-workspace {
    grid-template-columns: minmax(0, 1fr) 390px;
  }

  .lifecycle-primary {
    grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
    align-items: start;
  }
}
```

- [ ] **Step 5: Run lifecycle tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx src/lifecycle/CallSequence.test.tsx src/lifecycle/manifestValidation.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 6 and any deferred Task 4 or Task 5 files**

Run:

```bash
git add explorer/src/lifecycle/LifecycleExplorer.tsx explorer/src/lifecycle/LifecycleExplorer.test.tsx explorer/src/lifecycle/LifecycleDrawer.tsx explorer/src/lifecycle/LifecycleDiagram.tsx explorer/src/index.css
git commit -m "Wire lifecycle calls into explorer"
```

---

### Task 7: Final Verification And Build

**Files:**
- Inspect: `explorer/src/lifecycle/*.tsx`
- Inspect: `explorer/src/lifecycle/*.test.ts*`
- Inspect: `explorer/public/data/lifecycle/kilvin-asyncio-happy-path.json`

- [ ] **Step 1: Run lifecycle-focused tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle
```

Expected: PASS.

- [ ] **Step 2: Run full explorer verification**

Run:

```bash
cd explorer && npm run typecheck && npm test && npm run build
```

Expected: PASS for typecheck, all Vitest suites, and Vite production build.

- [ ] **Step 3: Inspect git diff for scope**

Run:

```bash
git diff --stat HEAD
git diff HEAD -- explorer/src/lifecycle explorer/public/data/lifecycle explorer/src/index.css
```

Expected: only lifecycle call sequence, lifecycle data, lifecycle tests, and lifecycle CSS changes appear.

- [ ] **Step 4: Commit final verification fixes if any were required**

Run only if Step 2 required changes after the Task 6 commit:

```bash
git add explorer/src/lifecycle explorer/public/data/lifecycle explorer/src/index.css explorer/src/control/ControlPathsExplorer.test.tsx
git commit -m "Verify lifecycle call sequence explorer"
```

---

## Self-Review Notes

- Spec coverage: The plan covers required `calls`, manifest validation, sorted timeline, phase highlighting, selected call drawer details, directed diagram edges, selectable edges, mobile/desktop layout CSS, and tests.
- Scope: The plan stays inside `explorer/`, lifecycle manifests, and lifecycle tests. It does not add runtime tracing or workflow execution.
- Type consistency: `LifecycleCall`, `LifecycleCallKind`, `LifecycleSelection`, `phase_id`, `edge_id`, `message`, `details`, and `payload` are used consistently across tests, components, and validation.
