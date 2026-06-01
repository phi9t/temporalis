# Control Paths Sticky Sequence Diagram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Control Paths into a sequence-driven explorer where scenario steps scroll beside a sticky lifecycle diagram with polished selected-edge labels.

**Architecture:** Add optional structured `steps` to control scenario manifests, normalize those steps in the control explorer, and reuse `LifecycleDiagram`'s selected-call rendering path by adapting each control step into a call-like object. Add a focused `ControlSequence` component for scenario rows and extend `LifecycleDrawer` to render control-step details without forking the lifecycle diagram.

**Tech Stack:** Python manifest generator, React 19, TypeScript, SVG, CSS, Vite, Vitest with jsdom, Testing Library, pytest.

---

## File Structure

- Modify `explorer/scripts/build_lifecycle_data.py`: add `control_step()` helper and `steps` arrays for each control scenario.
- Modify `tests/explorer/test_lifecycle_data.py`: validate control steps reference existing nodes/edges and preserve meaningful text.
- Modify `explorer/src/lifecycle/types.ts`: add `ControlStep`, `ControlStepKind`, and extend `ControlScenario`.
- Modify `explorer/src/control/ControlSequence.tsx`: new focused row list for ordered scenario steps.
- Modify `explorer/src/control/ControlPathsExplorer.tsx`: normalize steps, own selected step/node state, coordinate row reveal, and pass call-like selected/active labels to `LifecycleDiagram`.
- Modify `explorer/src/control/ControlPathsExplorer.test.tsx`: cover sequence rendering, default selection, edge selection, scroll behavior, scenario reset, and selected labels.
- Modify `explorer/src/lifecycle/LifecycleDrawer.tsx`: accept and render selected control-step details.
- Modify `explorer/src/index.css`: share lifecycle sequence visual language and add control workspace layout classes.

---

### Task 1: Structured Control Steps In Manifests

**Files:**
- Modify: `explorer/scripts/build_lifecycle_data.py`
- Modify: `tests/explorer/test_lifecycle_data.py`
- Modify: `explorer/src/lifecycle/types.ts`

- [ ] **Step 1: Write failing generator validation tests**

Modify `tests/explorer/test_lifecycle_data.py`.

Add this test after `test_control_path_overlays_reference_existing_nodes_and_edges`:

```python
def test_control_path_steps_reference_existing_nodes_and_edges() -> None:
    run_generator()
    lifecycle = load_json(OUT / "lifecycle" / "kilvin-asyncio-happy-path.json")
    node_ids = {node["id"] for node in lifecycle["nodes"]}
    edge_ids = {edge["id"] for edge in lifecycle["edges"]}
    index = json.loads((OUT / "control-paths" / "index.json").read_text(encoding="utf-8"))

    for entry in index:
        scenario = load_json(OUT / entry["manifest"])
        assert len(scenario["steps"]) >= 3
        seen_seq = set()
        for step in scenario["steps"]:
            assert step["id"].startswith(f"{scenario['slug']}-")
            assert step["seq"] not in seen_seq
            seen_seq.add(step["seq"])
            assert step["message"].strip()
            assert step["summary"].strip()
            assert len(step["details"]) >= 1
            assert set(step.get("affected_node_ids", [])) <= node_ids
            assert set(step.get("affected_edge_ids", [])) <= edge_ids
            if step.get("from") is not None:
                assert step["from"] in node_ids
            if step.get("to") is not None:
                assert step["to"] in node_ids
            if step.get("edge_id") is not None:
                assert step["edge_id"] in edge_ids
```

Extend `test_control_scenarios_have_guide_hack_links_and_details`:

```python
        assert len(scenario["steps"]) >= 3
        assert scenario["steps"][0]["seq"] == 1
```

- [ ] **Step 2: Run pytest to verify failure**

Run:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py::test_control_path_steps_reference_existing_nodes_and_edges tests/explorer/test_lifecycle_data.py::test_control_scenarios_have_guide_hack_links_and_details
```

Expected: FAIL with `KeyError: 'steps'`.

- [ ] **Step 3: Add the control step helper**

Modify `explorer/scripts/build_lifecycle_data.py`.

Add this helper after `call()`:

```python
def control_step(
    step_id: str,
    seq: int,
    kind: str,
    message: str,
    summary: str,
    details: list[str],
    *,
    source: str | None = None,
    target: str | None = None,
    edge_id: str | None = None,
    affected_node_ids: list[str] | None = None,
    affected_edge_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "seq": seq,
        "kind": kind,
        "from": source,
        "to": target,
        "edge_id": edge_id,
        "message": message,
        "summary": summary,
        "details": details,
        "affected_node_ids": affected_node_ids or [],
        "affected_edge_ids": affected_edge_ids or [],
    }
```

- [ ] **Step 4: Add structured steps to each control scenario**

Modify each scenario object inside `control_scenarios()` in `explorer/scripts/build_lifecycle_data.py`.

For `pause-resume`, add:

```python
            "steps": [
                control_step(
                    "pause-resume-signal-recorded",
                    1,
                    "signal",
                    "SignalWorkflowExecution",
                    "A pause or resume request enters workflow history through the server.",
                    [
                        "External control arrives as a signal or update instead of mutating worker memory directly.",
                        "History records the event so the control state survives worker restarts.",
                    ],
                    source="frontend-service",
                    target="history-service",
                    edge_id="frontend-history",
                    affected_node_ids=["frontend-service", "history-service"],
                    affected_edge_ids=["frontend-history"],
                ),
                control_step(
                    "pause-resume-activation",
                    2,
                    "activation",
                    "WorkflowActivation(signal/update)",
                    "The next activation delivers the durable control event to Python workflow code.",
                    [
                        "sdk-core includes the signal or update job in the activation.",
                        "Python workflow code updates deterministic pause state from that activation.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "pause-resume-command",
                    3,
                    "command",
                    "RespondWorkflowTaskCompleted",
                    "Python emits commands that either wait while paused or continue after resume.",
                    [
                        "The pause decision is encoded in deterministic workflow state.",
                        "Completion commands return through sdk-core and History like the happy path.",
                    ],
                    source="workflow-activation",
                    target="history-service",
                    edge_id="workflow-complete",
                    affected_node_ids=["workflow-activation", "history-service"],
                    affected_edge_ids=["workflow-complete", "schedule-wft"],
                ),
            ],
```

For `retry`, add:

```python
            "steps": [
                control_step(
                    "retry-failure",
                    1,
                    "failure",
                    "RespondActivityTaskFailed",
                    "The Python activity reports failure, timeout, or cancellation through sdk-core.",
                    [
                        "The failed attempt is not retried in Python user code directly.",
                        "The failure is reported back to the server as an activity completion outcome.",
                    ],
                    source="activity-task",
                    target="history-service",
                    edge_id="activity-complete",
                    affected_node_ids=["activity-task", "history-service"],
                    affected_edge_ids=["activity-complete"],
                ),
                control_step(
                    "retry-policy",
                    2,
                    "timer",
                    "Activity retry timer",
                    "History records the failed attempt and applies retry policy timing.",
                    [
                        "Retry state is durable server state.",
                        "Backoff determines when the next attempt becomes eligible.",
                    ],
                    source="history-service",
                    target="matching-service",
                    edge_id="activity-dispatch",
                    affected_node_ids=["history-service", "matching-service"],
                    affected_edge_ids=["activity-dispatch"],
                ),
                control_step(
                    "retry-dispatch",
                    3,
                    "task-dispatch",
                    "PollActivityTaskQueueResponse",
                    "Matching dispatches the next activity task attempt when the retry is due.",
                    [
                        "A worker poll receives the next attempt as normal activity work.",
                        "The retry re-enters Python through the same activity execution path.",
                    ],
                    source="matching-service",
                    target="activity-task",
                    edge_id="activity-dispatch",
                    affected_node_ids=["matching-service", "activity-task"],
                    affected_edge_ids=["activity-dispatch"],
                ),
            ],
```

For `replay`, add:

```python
            "steps": [
                control_step(
                    "replay-history-read",
                    1,
                    "history-event",
                    "GetWorkflowExecutionHistory",
                    "sdk-core reads durable history before accepting new workflow commands.",
                    [
                        "History is the authoritative log of prior workflow decisions.",
                        "Worker memory is an optimization, not the source of truth.",
                    ],
                    source="history-service",
                    target="core-worker",
                    edge_id="activation-up",
                    affected_node_ids=["history-service", "core-worker"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "replay-activation",
                    2,
                    "activation",
                    "WorkflowActivation(replay)",
                    "sdk-core replays history into Python workflow code deterministically.",
                    [
                        "Python re-executes workflow code to rebuild local state.",
                        "Activity side effects are not re-run during workflow replay.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "replay-command-check",
                    3,
                    "completion",
                    "RespondWorkflowTaskCompleted",
                    "New commands are accepted only after replay catches up to history.",
                    [
                        "Determinism requires replayed commands to match recorded history.",
                        "After catch-up, newly emitted commands can advance the execution.",
                    ],
                    source="workflow-activation",
                    target="history-service",
                    edge_id="workflow-complete",
                    affected_node_ids=["workflow-activation", "history-service"],
                    affected_edge_ids=["workflow-complete"],
                ),
            ],
```

For `heartbeat-cancellation`, add:

```python
            "steps": [
                control_step(
                    "heartbeat-progress",
                    1,
                    "heartbeat",
                    "RecordActivityTaskHeartbeat",
                    "The Python activity heartbeats progress while performing side effects.",
                    [
                        "Heartbeat details let retry resume with known progress.",
                        "Heartbeat cadence defines where cancellation can be observed.",
                    ],
                    source="activity-task",
                    target="core-worker",
                    edge_id="heartbeat",
                    affected_node_ids=["activity-task", "core-worker"],
                    affected_edge_ids=["heartbeat"],
                ),
                control_step(
                    "heartbeat-server-state",
                    2,
                    "heartbeat",
                    "RecordActivityTaskHeartbeatRequest",
                    "sdk-core forwards heartbeat details and receives cancellation state.",
                    [
                        "The server tracks the latest heartbeat details for the activity attempt.",
                        "Cancellation requested state can be delivered in the heartbeat response.",
                    ],
                    source="core-worker",
                    target="history-service",
                    edge_id="heartbeat",
                    affected_node_ids=["core-worker", "history-service"],
                    affected_edge_ids=["heartbeat"],
                ),
                control_step(
                    "heartbeat-cancel-complete",
                    3,
                    "completion",
                    "RespondActivityTaskCanceled",
                    "The activity reports cancellation after observing it at a heartbeat checkpoint.",
                    [
                        "Python cleanup runs at the activity boundary.",
                        "History records the canceled activity outcome durably.",
                    ],
                    source="activity-task",
                    target="history-service",
                    edge_id="activity-complete",
                    affected_node_ids=["activity-task", "history-service"],
                    affected_edge_ids=["activity-complete"],
                ),
            ],
```

For `sticky-cache-eviction`, add:

```python
            "steps": [
                control_step(
                    "sticky-cache-miss",
                    1,
                    "cache",
                    "Sticky cache miss",
                    "sdk-core discovers that warm workflow state is unavailable.",
                    [
                        "Sticky cache state is an optimization for faster activations.",
                        "Eviction or worker movement requires rebuilding from history.",
                    ],
                    source="matching-service",
                    target="core-worker",
                    edge_id="core-matching",
                    affected_node_ids=["matching-service", "core-worker"],
                    affected_edge_ids=["core-matching"],
                ),
                control_step(
                    "sticky-replay",
                    2,
                    "history-event",
                    "Replay from History",
                    "Core falls back to history replay because History is authoritative.",
                    [
                        "The replay path reconstructs workflow state without relying on sticky memory.",
                        "This keeps correctness independent of worker cache residency.",
                    ],
                    source="history-service",
                    target="core-worker",
                    edge_id="activation-up",
                    affected_node_ids=["history-service", "core-worker"],
                    affected_edge_ids=["activation-up"],
                ),
                control_step(
                    "sticky-rebuilt-activation",
                    3,
                    "activation",
                    "WorkflowActivation(rebuilt)",
                    "Python receives a rebuilt activation after core catches up to history.",
                    [
                        "The workflow continues with deterministic state restored.",
                        "Future tasks may become sticky again after the rebuilt activation.",
                    ],
                    source="core-worker",
                    target="workflow-activation",
                    edge_id="activation-up",
                    affected_node_ids=["core-worker", "workflow-activation"],
                    affected_edge_ids=["activation-up"],
                ),
            ],
```

- [ ] **Step 5: Add TypeScript control-step types**

Modify `explorer/src/lifecycle/types.ts`.

Add after `LifecycleCallKind`:

```ts
export type ControlStepKind =
  | LifecycleCallKind
  | 'signal'
  | 'failure'
  | 'timer'
  | 'cache'
```

Add after `LifecycleSelection`:

```ts
export interface ControlStep {
  id: string
  seq: number
  kind: ControlStepKind
  from: string | null
  to: string | null
  edge_id: string | null
  message: string
  summary: string
  details: string[]
  affected_node_ids: string[]
  affected_edge_ids: string[]
}

export type ControlSelection =
  | { type: 'control-step'; step: ControlStep }
  | { type: 'node'; node: LifecycleNode }
```

Extend `ControlScenario`:

```ts
  steps?: ControlStep[]
```

- [ ] **Step 6: Regenerate manifests and run validation**

Run:

```bash
python3 explorer/scripts/build_lifecycle_data.py --repo-root .
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py::test_control_path_steps_reference_existing_nodes_and_edges tests/explorer/test_lifecycle_data.py::test_control_scenarios_have_guide_hack_links_and_details
```

Expected: PASS.

- [ ] **Step 7: Commit structured data**

Run:

```bash
git add explorer/scripts/build_lifecycle_data.py tests/explorer/test_lifecycle_data.py explorer/src/lifecycle/types.ts explorer/public/data/control-paths
git commit -m "Model control path steps"
```

---

### Task 2: Control Sequence And Drawer Details

**Files:**
- Create: `explorer/src/control/ControlSequence.tsx`
- Modify: `explorer/src/control/ControlPathsExplorer.test.tsx`
- Modify: `explorer/src/lifecycle/LifecycleDrawer.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add failing UI tests for sequence and drawer**

Modify `explorer/src/control/ControlPathsExplorer.test.tsx`.

Update the test scenario fixture with `steps`:

```ts
  steps: [
    {
      id: 'pause-resume-signal-recorded',
      seq: 1,
      kind: 'signal',
      from: 'workflow-activation',
      to: 'history-service',
      edge_id: 'workflow-complete',
      message: 'SignalWorkflowExecution',
      summary: 'A pause request is recorded durably.',
      details: ['History stores the signal event.'],
      affected_node_ids: ['workflow-activation', 'history-service'],
      affected_edge_ids: ['workflow-complete'],
    },
    {
      id: 'pause-resume-activation',
      seq: 2,
      kind: 'activation',
      from: 'history-service',
      to: 'workflow-activation',
      edge_id: 'workflow-complete',
      message: 'WorkflowActivation(signal)',
      summary: 'The signal is delivered to workflow code.',
      details: ['Python updates deterministic pause state.'],
      affected_node_ids: ['workflow-activation', 'history-service'],
      affected_edge_ids: ['workflow-complete'],
    },
  ],
```

Add tests:

```tsx
it('renders an ordered control sequence and defaults to the first step details', async () => {
  render(<ControlPathsExplorer navigate={vi.fn()} />)

  const firstStep = await screen.findByRole('button', {
    name: /01 Activation to History SignalWorkflowExecution/,
  })

  expect(firstStep.getAttribute('aria-pressed')).toBe('true')
  expect(screen.getByLabelText('Control path sequence')).toBeTruthy()
  expect(screen.getByRole('heading', { name: 'SignalWorkflowExecution' })).toBeTruthy()
  expect(screen.getAllByText('A pause request is recorded durably.').length).toBeGreaterThan(0)
  expect(screen.getByText('History stores the signal event.')).toBeTruthy()
})

it('updates control step details when a sequence row is selected', async () => {
  render(<ControlPathsExplorer navigate={vi.fn()} />)

  const secondStep = await screen.findByRole('button', {
    name: /02 History to Activation WorkflowActivation\(signal\)/,
  })
  fireEvent.click(secondStep)

  expect(screen.getByRole('heading', { name: 'WorkflowActivation(signal)' })).toBeTruthy()
  expect(screen.getAllByText('The signal is delivered to workflow code.').length).toBeGreaterThan(0)
  expect(screen.getByText('Python updates deterministic pause state.')).toBeTruthy()
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd explorer && npm test -- --run src/control/ControlPathsExplorer.test.tsx
```

Expected: FAIL because `ControlSequence` and control-step drawer rendering do not exist.

- [ ] **Step 3: Create ControlSequence component**

Create `explorer/src/control/ControlSequence.tsx`:

```tsx
import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ControlStep } from '@/lifecycle/types'

function sequenceLabel(seq: number): string {
  return String(seq).padStart(2, '0')
}

function endpointLabel(nodeLabels: Map<string, string>, nodeId: string | null): string {
  if (!nodeId) return 'Control path'
  return nodeLabels.get(nodeId) ?? nodeId
}

export default function ControlSequence({
  steps,
  nodeLabels,
  selectedStepId,
  onSelect,
  registerStepRow,
}: {
  steps: ControlStep[]
  nodeLabels: Map<string, string>
  selectedStepId: string | null
  onSelect: (step: ControlStep) => void
  registerStepRow?: (stepId: string, element: HTMLButtonElement | null) => void
}) {
  const orderedSteps = [...steps].sort((a, b) => a.seq - b.seq)

  return (
    <section className="control-sequence call-sequence" aria-label="Control path sequence">
      <div className="call-sequence-header">
        <span>Control sequence</span>
      </div>
      <div className="call-sequence-list">
        {orderedSteps.map((step) => {
          const from = endpointLabel(nodeLabels, step.from)
          const to = endpointLabel(nodeLabels, step.to)
          const seq = sequenceLabel(step.seq)
          const selected = step.id === selectedStepId

          return (
            <button
              key={step.id}
              ref={(element) => registerStepRow?.(step.id, element)}
              type="button"
              data-control-step-id={step.id}
              className={cn('call-sequence-row', selected && 'selected')}
              aria-label={`${seq} ${from} to ${to} ${step.message}`}
              aria-pressed={selected}
              onClick={() => onSelect(step)}
            >
              <span className="call-sequence-seq">{seq}</span>
              <span className="call-sequence-body">
                <span className="call-sequence-route">
                  <span>{from}</span>
                  <ArrowRight size={14} strokeWidth={2} aria-hidden="true" />
                  <span>{to}</span>
                </span>
                <span className="call-sequence-message">{step.message}</span>
                <span className="call-sequence-summary">{step.summary}</span>
              </span>
              <span className="call-sequence-kind">{step.kind}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Extend LifecycleDrawer for control-step selection**

Modify the import in `explorer/src/lifecycle/LifecycleDrawer.tsx`:

```ts
import type {
  ControlSelection,
  ControlStep,
  LifecycleCall,
  LifecycleNode,
  LifecyclePhase,
  LifecycleSelection,
  SourceRef,
} from './types'
```

Add `ControlStepDetails` after `CallDetails`:

```tsx
function ControlStepDetails({
  step,
  nodeLabels,
}: {
  step: ControlStep
  nodeLabels: Map<string, string>
}) {
  const from = step.from ? (nodeLabels.get(step.from) ?? step.from) : 'Control path'
  const to = step.to ? (nodeLabels.get(step.to) ?? step.to) : 'Control path'

  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.message}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {from} -&gt; {to}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="call-detail-meta">
          <span>{step.kind}</span>
          <span>Control path</span>
        </div>
        <p className="text-ink">{step.summary}</p>
        <ul className="call-detail-list">
          {step.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
```

Update the prop type:

```ts
  selection?: LifecycleSelection | ControlSelection | null
```

Add before the existing `selected.type === 'call'` branch:

```tsx
  if (selected.type === 'control-step') {
    return <ControlStepDetails step={selected.step} nodeLabels={nodeLabels} />
  }
```

- [ ] **Step 5: Add minimal control sequence CSS**

Modify `explorer/src/index.css`.

Add near existing call sequence styles:

```css
.control-sequence .call-sequence-header span {
  color: var(--color-ink);
}
```

- [ ] **Step 6: Run UI tests**

Run:

```bash
cd explorer && npm test -- --run src/control/ControlPathsExplorer.test.tsx
```

Expected: still FAIL until `ControlPathsExplorer` renders `ControlSequence`; the drawer type changes should compile after the next task.

- [ ] **Step 7: Keep groundwork uncommitted for Task 3**

Do not commit after this task. The failing `ControlPathsExplorer.test.tsx` changes from Step 1 are
intentional red tests that Task 3 will make pass. Confirm the expected files are dirty:

```bash
git status --short
```

Expected: `ControlSequence.tsx`, `LifecycleDrawer.tsx`, `index.css`, and
`ControlPathsExplorer.test.tsx` are listed.

---

### Task 3: Control Explorer Coordination

**Files:**
- Modify: `explorer/src/control/ControlPathsExplorer.tsx`
- Modify: `explorer/src/control/ControlPathsExplorer.test.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add failing interaction tests**

Modify `explorer/src/control/ControlPathsExplorer.test.tsx`.

Add `beforeEach` if it is not already present:

```ts
const scrollIntoView = vi.fn()

beforeEach(() => {
  scrollIntoView.mockClear()
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: scrollIntoView,
  })
})
```

Add tests:

```tsx
it('selects the nearest matching control step when a diagram edge is selected', async () => {
  render(<ControlPathsExplorer navigate={vi.fn()} />)

  await screen.findByRole('button', {
    name: /01 Activation to History SignalWorkflowExecution/,
  })

  scrollIntoView.mockClear()
  const edge = screen.getByRole('button', { name: /Diagram edge RespondWorkflowTaskCompleted/ })
  fireEvent.keyDown(edge, { key: 'Enter' })

  expect(screen.getByRole('heading', { name: 'SignalWorkflowExecution' })).toBeTruthy()
  expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', behavior: 'auto' })
})

it('does not change selection merely because the control sequence scrolls', async () => {
  render(<ControlPathsExplorer navigate={vi.fn()} />)

  const sequence = await screen.findByLabelText('Control path sequence')
  fireEvent.scroll(sequence)

  expect(screen.getByRole('heading', { name: 'SignalWorkflowExecution' })).toBeTruthy()
})

it('uses the selected control step message as the diagram edge label', async () => {
  render(<ControlPathsExplorer navigate={vi.fn()} />)

  await screen.findByRole('heading', { name: 'SignalWorkflowExecution' })

  expect(screen.getByText('SignalWorkflowExecution')).toBeTruthy()
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd explorer && npm test -- --run src/control/ControlPathsExplorer.test.tsx
```

Expected: FAIL because `ControlPathsExplorer` has no selected step state, sequence rendering, or edge-to-step selection.

- [ ] **Step 3: Update ControlPathsExplorer imports and state**

Modify `explorer/src/control/ControlPathsExplorer.tsx`.

Change imports:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ControlSequence from './ControlSequence'
import type { ControlScenario, ControlSelection, ControlStep, LifecycleCall, LifecycleManifest, LifecycleNode } from '@/lifecycle/types'
```

Replace selected state:

```tsx
const [selected, setSelected] = useState<ControlSelection | null>(null)
const stepRowsRef = useRef(new Map<string, HTMLButtonElement>())
const shouldScrollSelectedStepRef = useRef(false)
```

- [ ] **Step 4: Add fallback normalization and call adapter**

Add these helpers above the component:

```tsx
function fallbackSteps(scenario: ControlScenario): ControlStep[] {
  return scenario.details.map((detail, index) => ({
    id: `${scenario.slug}-detail-${index + 1}`,
    seq: index + 1,
    kind: 'signal',
    from: null,
    to: null,
    edge_id: null,
    message: detail,
    summary: detail,
    details: [detail],
    affected_node_ids: scenario.highlight_node_ids,
    affected_edge_ids: scenario.highlight_edge_ids,
  }))
}

function stepToCall(step: ControlStep): LifecycleCall | null {
  if (!step.from || !step.to || !step.edge_id) return null

  return {
    id: step.id,
    phase_id: 'control-path',
    seq: step.seq,
    from: step.from,
    to: step.to,
    edge_id: step.edge_id,
    kind: step.kind,
    message: step.message,
    summary: step.summary,
    details: step.details,
    payload: [],
    refs: [],
  }
}
```

- [ ] **Step 5: Add selection and scroll coordination**

Inside `ControlPathsExplorer`, add after `entry`:

```tsx
const controlSteps = useMemo(() => (scenario ? [...(scenario.steps ?? fallbackSteps(scenario))].sort((a, b) => a.seq - b.seq) : []), [scenario])
const selectedStep = selected?.type === 'control-step' ? selected.step : null
const selectedNode = selected?.type === 'node' ? selected.node : null
const selectedCall = selectedStep ? stepToCall(selectedStep) : null
```

Add:

```tsx
const registerStepRow = useCallback((stepId: string, element: HTMLButtonElement | null) => {
  if (element) {
    stepRowsRef.current.set(stepId, element)
    return
  }

  stepRowsRef.current.delete(stepId)
}, [])

const selectStep = useCallback((step: ControlStep) => {
  setSelected({ type: 'control-step', step })
}, [])

const selectStepAndReveal = useCallback((step: ControlStep) => {
  shouldScrollSelectedStepRef.current = true
  selectStep(step)
}, [selectStep])

function handleEdgeSelect(edgeId: string) {
  const step = controlSteps.find((item) => item.edge_id === edgeId || item.affected_edge_ids.includes(edgeId))

  if (step) {
    selectStepAndReveal(step)
  }
}
```

Add effects:

```tsx
useEffect(() => {
  stepRowsRef.current.clear()
}, [slug])

useEffect(() => {
  if (!scenario || controlSteps.length === 0) {
    setSelected(null)
    return
  }

  setSelected({ type: 'control-step', step: controlSteps[0] })
}, [scenario, controlSteps])

useEffect(() => {
  if (!selectedStep || !shouldScrollSelectedStepRef.current) return

  shouldScrollSelectedStepRef.current = false
  stepRowsRef.current.get(selectedStep.id)?.scrollIntoView({ block: 'nearest', behavior: 'auto' })
}, [selectedStep])
```

- [ ] **Step 6: Render sequence, diagram, and drawer from selected step**

Replace the existing `activeNodeIds` and `activeEdgeIds` memos:

```tsx
const activeNodeIds = useMemo(
  () => new Set([...(scenario?.highlight_node_ids ?? []), ...(selectedStep?.affected_node_ids ?? [])]),
  [scenario, selectedStep],
)
const activeEdgeIds = useMemo(
  () => new Set([...(scenario?.highlight_edge_ids ?? []), ...(selectedStep?.affected_edge_ids ?? [])]),
  [scenario, selectedStep],
)
const nodeLabels = useMemo(() => new Map(lifecycle?.nodes.map((node) => [node.id, node.label]) ?? []), [lifecycle])
const activeCallLabels = useMemo(() => controlSteps.map(stepToCall).filter((call): call is LifecycleCall => call !== null), [controlSteps])
const selectedEndpointNodeIds = useMemo(
  () => new Set([selectedStep?.from, selectedStep?.to].filter((id): id is string => Boolean(id))),
  [selectedStep],
)
```

Replace the existing `control-details` list and adjacent `LifecycleDiagram` block with:

```tsx
<div className="control-main lifecycle-main">
  <div className="control-sequence-shell lifecycle-sequence">
    <ControlSequence
      steps={controlSteps}
      nodeLabels={nodeLabels}
      selectedStepId={selectedStep?.id ?? null}
      onSelect={selectStep}
      registerStepRow={registerStepRow}
    />
  </div>
  <div className="control-diagram-shell lifecycle-diagram">
    <LifecycleDiagram
      nodes={lifecycle.nodes}
      edges={lifecycle.edges}
      activeNodeIds={activeNodeIds}
      activeEdgeIds={activeEdgeIds}
      selectedId={selectedNode?.id ?? null}
      selectedEdgeId={selectedStep?.edge_id ?? null}
      selectedCallFrom={selectedStep?.from ?? null}
      selectedCallTo={selectedStep?.to ?? null}
      selectedCall={selectedCall}
      activeCallLabels={activeCallLabels}
      activePhaseId="control-path"
      selectedEndpointNodeIds={selectedEndpointNodeIds}
      onSelect={(node) => setSelected({ type: 'node', node })}
      onSelectEdge={handleEdgeSelect}
    />
  </div>
</div>
```

Update the drawer:

```tsx
<LifecycleDrawer selection={selected} phase={null} nodeLabels={nodeLabels} />
```

- [ ] **Step 7: Add control workspace CSS**

Modify `explorer/src/index.css`.

Add:

```css
.control-main {
  display: grid;
  gap: 18px;
  align-items: start;
}

@media (min-width: 1280px) {
  .control-main {
    grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
    max-height: min(760px, calc(100vh - 180px));
  }
}
```

- [ ] **Step 8: Run control tests**

Run:

```bash
cd explorer && npm test -- --run src/control/ControlPathsExplorer.test.tsx
```

Expected: PASS.

- [ ] **Step 9: Commit sequence, drawer, and explorer coordination**

Run:

```bash
git add explorer/src/control/ControlSequence.tsx explorer/src/control/ControlPathsExplorer.tsx explorer/src/control/ControlPathsExplorer.test.tsx explorer/src/lifecycle/LifecycleDrawer.tsx explorer/src/index.css
git commit -m "Coordinate control path sequence with diagram"
```

---

### Task 4: Verification And Polish

**Files:**
- Modify only files needed to fix failures found by verification.

- [ ] **Step 1: Run lifecycle and control focused tests**

Run:

```bash
cd explorer && npm test -- --run src/control src/lifecycle
```

Expected: PASS.

- [ ] **Step 2: Run TypeScript and lint**

Run:

```bash
cd explorer && npm run typecheck
cd explorer && npm run lint
```

Expected: both PASS.

- [ ] **Step 3: Run Python manifest tests**

Run:

```bash
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py
```

Expected: PASS.

- [ ] **Step 4: Regenerate manifests and verify no accidental drift**

Run:

```bash
python3 explorer/scripts/build_lifecycle_data.py --repo-root .
git status --short
```

Expected: no unexpected files. Expected generated control manifests are already tracked from Task 1.

- [ ] **Step 5: Build the explorer**

Run:

```bash
cd explorer && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit verification fixes if needed**

If Step 1-5 required any fixes, commit only those files:

Run `git status --short`, inspect the exact files changed by the fixes, then commit those files with
`git add` and `git commit -m "Polish control path sequence rendering"`.

If no fixes were needed, do not create an empty commit.
