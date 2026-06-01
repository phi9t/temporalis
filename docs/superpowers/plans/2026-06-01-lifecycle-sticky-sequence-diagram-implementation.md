# Lifecycle Sticky Sequence Diagram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the lifecycle diagram visually paired with the call sequence while improving edge label readability and polish.

**Architecture:** Add scroll coordination to `LifecycleExplorer` with refs on selected call rows, keeping desktop sequence scrolling independent from the sticky diagram. Move edge label decision and placement logic into small pure helpers in `LifecycleDiagram` so selected-call labels use call messages, active labels stay restrained, and tests can verify geometry/text behavior without brittle DOM-only checks.

**Tech Stack:** React 19, TypeScript, SVG, CSS, Vite, Vitest with jsdom, Testing Library.

---

## File Structure

- Modify `explorer/src/lifecycle/CallSequence.tsx`: accept selected row refs and expose call row ids for scroll alignment.
- Modify `explorer/src/lifecycle/LifecycleExplorer.tsx`: own the selected call row refs, scroll selected calls into view after phase/edge selection, and preserve no-auto-select-on-scroll.
- Modify `explorer/src/lifecycle/LifecycleDiagram.tsx`: add selected-call label text, active-call label lookup, label truncation, badge placement, and SVG label badge rendering.
- Modify `explorer/src/lifecycle/LifecycleExplorer.test.tsx`: cover selected-call scroll behavior and no scroll-driven selection behavior.
- Create `explorer/src/lifecycle/LifecycleDiagram.test.tsx`: unit test exported label helpers for truncation, selected-call precedence, active-call fallback, and placement clamping.
- Modify `explorer/src/index.css`: add desktop sticky/scroll layout and refined edge label badge styles.

---

### Task 1: Sticky Diagram And Scrollable Sequence

**Files:**
- Modify: `explorer/src/lifecycle/CallSequence.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.test.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add failing scroll coordination tests**

Modify `explorer/src/lifecycle/LifecycleExplorer.test.tsx`.

Add `beforeEach` beside the existing `afterEach`:

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

Add this test after `keeps the active phase and guide aligned when selecting a call from another phase`:

```tsx
it('scrolls the selected call into view when phase or edge selection changes it', async () => {
  render(<LifecycleExplorer navigate={vi.fn()} />)

  await screen.findByRole('button', {
    name: /01 Kilvin client to Frontend StartWorkflowExecution/,
  })

  scrollIntoView.mockClear()
  fireEvent.click(screen.getByRole('button', { name: 'Poll workflow task' }))

  expect(screen.getByRole('heading', { name: 'PollWorkflowTaskQueue' })).toBeTruthy()
  expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', behavior: 'auto' })

  scrollIntoView.mockClear()
  fireEvent.click(screen.getByRole('button', { name: 'Start workflow' }))
  expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()

  const edge = screen.getByRole('button', { name: /Diagram edge StartWorkflowExecution/ })
  fireEvent.keyDown(edge, { key: 'Enter' })

  expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', behavior: 'auto' })
})
```

Add this test after the new test:

```tsx
it('does not change selection merely because the call sequence scrolls', async () => {
  render(<LifecycleExplorer navigate={vi.fn()} />)

  const sequence = await screen.findByLabelText('Lifecycle call sequence')
  fireEvent.scroll(sequence)

  expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: FAIL because selected call rows are not registered and `scrollIntoView` is not called after phase/edge selection.

- [ ] **Step 3: Add row ref support to CallSequence**

Modify `explorer/src/lifecycle/CallSequence.tsx`.

Change the component props:

```tsx
export default function CallSequence({
  calls,
  nodeLabels,
  activePhaseId,
  selectedCallId,
  onSelect,
  registerCallRow,
}: {
  calls: LifecycleCall[]
  nodeLabels: Map<string, string>
  activePhaseId: string
  selectedCallId: string | null
  onSelect: (call: LifecycleCall) => void
  registerCallRow?: (callId: string, element: HTMLButtonElement | null) => void
}) {
```

Add `ref` and `data-call-id` to the call row button:

```tsx
<button
  key={call.id}
  ref={(element) => registerCallRow?.(call.id, element)}
  type="button"
  data-call-id={call.id}
  className={cn('call-sequence-row', active && 'active', selected && 'selected')}
  aria-label={`${seq} ${from} to ${to} ${call.message}${active ? ' Current phase call' : ''}`}
  aria-pressed={selected}
  data-active-phase={active}
  onClick={() => onSelect(call)}
>
```

- [ ] **Step 4: Add scroll coordination in LifecycleExplorer**

Modify `explorer/src/lifecycle/LifecycleExplorer.tsx`.

Change the React import:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
```

Add refs after state declarations:

```tsx
const callRowsRef = useRef(new Map<string, HTMLButtonElement>())
const shouldScrollSelectedCallRef = useRef(false)
```

Add helpers after `selectCall`:

```tsx
const registerCallRow = useCallback((callId: string, element: HTMLButtonElement | null) => {
  if (element) {
    callRowsRef.current.set(callId, element)
    return
  }

  callRowsRef.current.delete(callId)
}, [])

const selectCallAndReveal = useCallback((call: LifecycleCall) => {
  shouldScrollSelectedCallRef.current = true
  selectCall(call)
}, [selectCall])
```

Add effect after selected call computation:

```tsx
useEffect(() => {
  if (!selectedCall || !shouldScrollSelectedCallRef.current) return

  shouldScrollSelectedCallRef.current = false
  callRowsRef.current.get(selectedCall.id)?.scrollIntoView({ block: 'nearest', behavior: 'auto' })
}, [selectedCall])
```

Update phase and edge selection to use `selectCallAndReveal`:

```tsx
function handleEdgeSelect(edgeId: string) {
  const call = activePhaseCalls.find((item) => item.edge_id === edgeId) ?? calls.find((item) => item.edge_id === edgeId)

  if (call) {
    selectCallAndReveal(call)
  }
}

function handlePhaseChange(nextPhaseId: string) {
  const call = calls.find((item) => item.phase_id === nextPhaseId)

  if (call) {
    selectCallAndReveal(call)
    return
  }

  setPhaseId(nextPhaseId)
  setSelected(null)
}
```

Keep direct call-row selection as `selectCall` so clicking visible rows does not trigger unnecessary scrolling:

```tsx
<CallSequence
  calls={calls}
  nodeLabels={nodeLabels}
  activePhaseId={phase?.id ?? ''}
  selectedCallId={selectedCall?.id ?? null}
  onSelect={selectCall}
  registerCallRow={registerCallRow}
/>
```

- [ ] **Step 5: Add desktop sticky and sequence scroll CSS**

Modify `explorer/src/index.css`.

Update the desktop media query:

```css
@media (min-width: 1280px) {
  .lifecycle-workspace {
    grid-template-columns: minmax(0, 1fr) 390px;
  }

  .lifecycle-main {
    grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
    max-height: min(760px, calc(100vh - 180px));
  }

  .lifecycle-diagram {
    order: 1;
    position: sticky;
    top: 24px;
    align-self: start;
  }

  .lifecycle-sequence {
    order: 2;
    max-height: min(760px, calc(100vh - 180px));
    overflow-y: auto;
    overscroll-behavior: contain;
    padding-right: 4px;
  }

  .lifecycle-drawer-shell {
    position: sticky;
    top: 24px;
  }
}
```

Add scrollbar styling near the call sequence block:

```css
.lifecycle-sequence {
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) transparent;
}

.lifecycle-sequence::-webkit-scrollbar {
  width: 8px;
}

.lifecycle-sequence::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: var(--scrollbar-thumb);
}
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleExplorer.test.tsx src/lifecycle/CallSequence.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Run typecheck and lint**

Run:

```bash
cd explorer && npm run typecheck && npm run lint
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add explorer/src/lifecycle/CallSequence.tsx explorer/src/lifecycle/LifecycleExplorer.tsx explorer/src/lifecycle/LifecycleExplorer.test.tsx explorer/src/index.css
git commit -m "Keep lifecycle diagram paired with sequence"
```

---

### Task 2: Edge Label Selection, Placement, And Badge Rendering

**Files:**
- Modify: `explorer/src/lifecycle/LifecycleDiagram.tsx`
- Create: `explorer/src/lifecycle/LifecycleDiagram.test.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.tsx`
- Modify: `explorer/src/lifecycle/LifecycleExplorer.test.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add failing helper tests**

Create `explorer/src/lifecycle/LifecycleDiagram.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest'
import {
  displayEdgeLabel,
  edgeLabelPlacement,
  truncateEdgeLabel,
  type EdgeLabelCall,
} from './LifecycleDiagram'

const calls: EdgeLabelCall[] = [
  {
    id: 'call-core-poll',
    seq: 6,
    phase_id: 'poll',
    edge_id: 'core-matching',
    message: 'PollWorkflowTaskQueue',
  },
  {
    id: 'call-matching-response',
    seq: 7,
    phase_id: 'poll',
    edge_id: 'core-matching',
    message: 'workflow task response',
  },
  {
    id: 'call-activity-complete',
    seq: 16,
    phase_id: 'execute-activity',
    edge_id: 'core-frontend',
    message: 'RespondActivityTaskCompleted',
  },
]

describe('LifecycleDiagram edge labels', () => {
  it('uses the selected call message for selected edges', () => {
    expect(
      displayEdgeLabel({
        edgeId: 'core-matching',
        edgeLabel: 'PollWorkflowTaskQueue',
        activeCallLabels: calls,
        selectedCall: calls[1],
        activePhaseId: 'poll',
      }),
    ).toEqual({
      text: 'workflow task response',
      fullText: 'workflow task response',
      visible: true,
      selected: true,
    })
  })

  it('uses the nearest active phase call for non-selected active edges', () => {
    expect(
      displayEdgeLabel({
        edgeId: 'core-matching',
        edgeLabel: 'PollWorkflowTaskQueue',
        activeCallLabels: calls,
        selectedCall: calls[2],
        activePhaseId: 'poll',
      })?.fullText,
    ).toBe('workflow task response')
  })

  it('truncates long visible labels while preserving full text', () => {
    expect(truncateEdgeLabel('RespondWorkflowTaskCompletedWithVeryLongDiagnosticSuffix')).toBe(
      'RespondWorkflowTaskComplet...',
    )
  })

  it('places vertical labels to the side and clamps them into the viewbox', () => {
    expect(
      edgeLabelPlacement({
        x1: 250,
        y1: 90,
        x2: 250,
        y2: 480,
        labelWidth: 210,
        labelHeight: 24,
        viewBoxWidth: 820,
        viewBoxHeight: 560,
      }),
    ).toEqual({ x: 268, y: 273 })
  })

  it('places horizontal labels above the midpoint and clamps left overflow', () => {
    expect(
      edgeLabelPlacement({
        x1: 20,
        y1: 120,
        x2: 160,
        y2: 120,
        labelWidth: 220,
        labelHeight: 24,
        viewBoxWidth: 820,
        viewBoxHeight: 560,
      }),
    ).toEqual({ x: 8, y: 84 })
  })
})
```

- [ ] **Step 2: Run helper tests to verify failure**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleDiagram.test.tsx
```

Expected: FAIL because the helpers are not exported.

- [ ] **Step 3: Add label helper exports to LifecycleDiagram**

Modify `explorer/src/lifecycle/LifecycleDiagram.tsx`.

Update imports:

```tsx
import { cn } from '@/lib/utils'
import type { LifecycleCall, LifecycleEdge, LifecycleNode } from './types'
```

Add helper types and functions above the component:

```tsx
const EDGE_LABEL_MAX = 28
const EDGE_LABEL_CHAR_WIDTH = 6.5
const EDGE_LABEL_HEIGHT = 24
const EDGE_LABEL_PADDING_X = 16
const EDGE_LABEL_RADIUS = 6
const SVG_WIDTH = 820
const SVG_HEIGHT = 560

export interface EdgeLabelCall {
  id: string
  seq: number
  phase_id: string
  edge_id: string
  message: string
}

export interface DisplayEdgeLabel {
  text: string
  fullText: string
  visible: boolean
  selected: boolean
}

export function truncateEdgeLabel(label: string): string {
  if (label.length <= EDGE_LABEL_MAX) return label
  return `${label.slice(0, EDGE_LABEL_MAX - 3)}...`
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function edgeLabelPlacement({
  x1,
  y1,
  x2,
  y2,
  labelWidth,
  labelHeight,
  viewBoxWidth,
  viewBoxHeight,
}: {
  x1: number
  y1: number
  x2: number
  y2: number
  labelWidth: number
  labelHeight: number
  viewBoxWidth: number
  viewBoxHeight: number
}) {
  const midX = (x1 + x2) / 2
  const midY = (y1 + y2) / 2
  const mostlyVertical = Math.abs(y2 - y1) > Math.abs(x2 - x1) * 1.25
  const rawX = mostlyVertical ? midX + 18 : midX - labelWidth / 2
  const rawY = mostlyVertical ? midY - labelHeight / 2 : midY - labelHeight - 12

  return {
    x: Math.round(clamp(rawX, 8, viewBoxWidth - labelWidth - 8)),
    y: Math.round(clamp(rawY, 8, viewBoxHeight - labelHeight - 8)),
  }
}

export function displayEdgeLabel({
  edgeId,
  edgeLabel,
  activeCallLabels,
  selectedCall,
  activePhaseId,
}: {
  edgeId: string
  edgeLabel: string
  activeCallLabels: EdgeLabelCall[]
  selectedCall: EdgeLabelCall | null
  activePhaseId: string
}): DisplayEdgeLabel | null {
  if (selectedCall?.edge_id === edgeId) {
    return {
      text: truncateEdgeLabel(selectedCall.message),
      fullText: selectedCall.message,
      visible: true,
      selected: true,
    }
  }

  const activeCalls = activeCallLabels
    .filter((call) => call.phase_id === activePhaseId && call.edge_id === edgeId)
    .sort((a, b) => {
      if (!selectedCall) return a.seq - b.seq
      return Math.abs(a.seq - selectedCall.seq) - Math.abs(b.seq - selectedCall.seq)
    })

  const activeCall = activeCalls[0]
  if (!activeCall) return null

  const fullText = activeCall.message || edgeLabel

  return {
    text: truncateEdgeLabel(fullText),
    fullText,
    visible: fullText.length <= 48,
    selected: false,
  }
}

function edgeLabelWidth(text: string): number {
  return Math.round(text.length * EDGE_LABEL_CHAR_WIDTH + EDGE_LABEL_PADDING_X)
}
```

- [ ] **Step 4: Wire selected and active call labels into LifecycleDiagram**

Change `LifecycleDiagram` props:

```tsx
  selectedCall = null,
  activeCallLabels = [],
  activePhaseId,
```

Add prop types:

```tsx
  selectedCall?: EdgeLabelCall | null
  activeCallLabels?: EdgeLabelCall[]
  activePhaseId: string
```

Inside edge rendering, replace the existing text label block with badge rendering:

```tsx
const label = displayEdgeLabel({
  edgeId: edge.id,
  edgeLabel: edge.label,
  activeCallLabels,
  selectedCall,
  activePhaseId,
})
const labelWidth = label ? edgeLabelWidth(label.text) : 0
const labelPosition =
  label && label.visible
    ? edgeLabelPlacement({
        x1: a.cx,
        y1: a.cy,
        x2: b.cx,
        y2: b.cy,
        labelWidth,
        labelHeight: EDGE_LABEL_HEIGHT,
        viewBoxWidth: SVG_WIDTH,
        viewBoxHeight: SVG_HEIGHT,
      })
    : null
```

Render this inside the edge group after lines:

```tsx
{label && labelPosition && (
  <g className={cn('lifecycle-edge-label-badge', label.selected && 'selected')}>
    <rect
      x={labelPosition.x}
      y={labelPosition.y}
      width={labelWidth}
      height={EDGE_LABEL_HEIGHT}
      rx={EDGE_LABEL_RADIUS}
    />
    <text x={labelPosition.x + labelWidth / 2} y={labelPosition.y + 16} textAnchor="middle">
      {label.text}
    </text>
    <title>{label.fullText}</title>
  </g>
)}
```

Update edge group accessible label to use full selected/active label where available:

```tsx
aria-label={selectable ? `Diagram edge ${label?.fullText ?? edge.label}` : undefined}
```

- [ ] **Step 5: Pass call label data from LifecycleExplorer**

Modify `explorer/src/lifecycle/LifecycleExplorer.tsx`.

Pass props to `LifecycleDiagram`:

```tsx
<LifecycleDiagram
  nodes={manifest.nodes}
  edges={manifest.edges}
  activeNodeIds={activeNodeIds}
  activeEdgeIds={activeEdgeIds}
  selectedId={selectedNode?.id ?? null}
  selectedEdgeId={selectedCall?.edge_id ?? null}
  selectedCallFrom={selectedCall?.from ?? null}
  selectedCallTo={selectedCall?.to ?? null}
  selectedCall={selectedCall}
  activeCallLabels={calls}
  activePhaseId={phase?.id ?? ''}
  selectedEndpointNodeIds={selectedEndpointNodeIds}
  onSelect={(node) => setSelected({ type: 'node', node })}
  onSelectEdge={handleEdgeSelect}
/>
```

- [ ] **Step 6: Replace edge label CSS**

Modify `explorer/src/index.css`.

Replace `.lifecycle-edge-label` with:

```css
.lifecycle-edge-label-badge {
  pointer-events: none;
}

.lifecycle-edge-label-badge rect {
  fill: rgba(7, 10, 19, 0.86);
  stroke: rgba(148, 163, 184, 0.22);
  stroke-width: 1;
  filter: drop-shadow(0 6px 14px rgba(0, 0, 0, 0.28));
}

.lifecycle-edge-label-badge text {
  fill: var(--color-ink-soft);
  font-size: 10px;
  font-weight: 700;
}

.lifecycle-edge-label-badge.selected rect {
  fill: rgba(15, 23, 42, 0.96);
  stroke: rgba(56, 189, 248, 0.72);
}

.lifecycle-edge-label-badge.selected text {
  fill: var(--color-ink);
}
```

- [ ] **Step 7: Add integration assertions for selected edge label text**

Modify `explorer/src/lifecycle/LifecycleExplorer.test.tsx`.

In `renders selected response calls in call direction on reused edges`, add:

```tsx
expect(screen.getByText('StartWorkflowExecutionResponse')).toBeTruthy()
expect(screen.getByRole('button', { name: /Diagram edge StartWorkflowExecutionResponse/ })).toBeTruthy()
```

In `selects the first active-phase call when a diagram edge is clicked`, after the final assertion add:

```tsx
expect(screen.getByText('StartWorkflowExecution')).toBeTruthy()
```

- [ ] **Step 8: Run diagram tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle/LifecycleDiagram.test.tsx src/lifecycle/LifecycleExplorer.test.tsx
```

Expected: PASS.

- [ ] **Step 9: Run typecheck and lint**

Run:

```bash
cd explorer && npm run typecheck && npm run lint
```

Expected: PASS.

- [ ] **Step 10: Commit Task 2**

Run:

```bash
git add explorer/src/lifecycle/LifecycleDiagram.tsx explorer/src/lifecycle/LifecycleDiagram.test.tsx explorer/src/lifecycle/LifecycleExplorer.tsx explorer/src/lifecycle/LifecycleExplorer.test.tsx explorer/src/index.css
git commit -m "Refine lifecycle diagram edge labels"
```

---

### Task 3: Final Verification

**Files:**
- Inspect: `explorer/src/lifecycle/CallSequence.tsx`
- Inspect: `explorer/src/lifecycle/LifecycleDiagram.tsx`
- Inspect: `explorer/src/lifecycle/LifecycleExplorer.tsx`
- Inspect: `explorer/src/index.css`

- [ ] **Step 1: Run lifecycle-focused tests**

Run:

```bash
cd explorer && npm test -- --run src/lifecycle
```

Expected: PASS with all lifecycle test files passing.

- [ ] **Step 2: Run full explorer verification**

Run:

```bash
cd explorer && npm run typecheck && npm test && npm run lint && npm run build
```

Expected: PASS for TypeScript, Vitest, ESLint, and Vite production build.

- [ ] **Step 3: Confirm no generator drift or unrelated changes**

Run:

```bash
python3 explorer/scripts/build_lifecycle_data.py --repo-root .
git status --short
```

Expected: no lifecycle data drift. Only intended source/test/CSS changes should appear before the final commit, and the worktree should be clean after all commits.

- [ ] **Step 4: Manual desktop acceptance**

Run:

```bash
cd explorer && npm run dev -- --host 127.0.0.1
```

Expected:

- Dev server starts with a local URL.
- On desktop width, the diagram remains visible while the call sequence scrolls.
- Selecting a phase or diagram edge scrolls the selected row into view.
- Selected edge label uses the selected call message.
- Response calls show the correct edge direction and label.
- There is no label soup in the happy-path lifecycle.

Stop the dev server after manual inspection.

- [ ] **Step 5: Commit verification fixes if needed**

Run only if Step 1-4 required fixes:

```bash
git add explorer/src/lifecycle explorer/src/index.css
git commit -m "Verify lifecycle sticky sequence diagram"
```

---

## Self-Review Notes

- Spec coverage: Task 1 covers sticky diagram, independently scrollable sequence, selected row reveal, mobile natural flow, keyboard-safe focus behavior, and no auto-select-on-scroll. Task 2 covers selected/active/inactive edge rendering, selected call label text, direction-aware label placement, badge aesthetics, truncation, full accessible text, and tests. Task 3 covers final verification and manual acceptance.
- Scope: The plan stays inside lifecycle UI, lifecycle tests, and CSS. It does not change manifest schema or generator semantics.
- Type consistency: `registerCallRow`, `selectedCall`, `activeCallLabels`, `activePhaseId`, `EdgeLabelCall`, `displayEdgeLabel`, `truncateEdgeLabel`, and `edgeLabelPlacement` are used consistently across planned component and test changes.
