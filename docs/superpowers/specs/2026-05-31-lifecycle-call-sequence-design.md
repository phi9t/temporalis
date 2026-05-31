# Lifecycle Call Sequence Design

## Summary

Improve the Temporal Explorer lifecycle visualization so it explains call order, direction, and
messages between the Kilvin app, Python SDK, bridge, sdk-core, and Temporal server.

The current lifecycle diagram shows connected components, but the line graph does not explain which
component calls which, when each call happens, or what message crosses the boundary. The upgrade
adds a first-class ordered call sequence and uses the existing swimlane diagram as a coordinated
spatial map.

## Product Shape

The lifecycle page will have three coordinated explanation surfaces:

- **Phase tabs** keep the current high-level walkthrough: start workflow, poll task queue, activate
  workflow, schedule activity, execute activity, and complete turn.
- **Call Sequence panel** becomes the authoritative timeline. It shows numbered calls/messages in
  lifecycle order and highlights the calls that belong to the selected phase.
- **Swimlane diagram** remains the map of app, SDK, bridge, core, and server components. It adds
  visible direction, selected-edge emphasis, and synchronization with the selected call.

The timeline is the source of truth for time and ordering. The diagram should not try to encode
sequence by itself because crossing swimlane edges are poor at teaching order.

## User Interaction

Users can select either a call or a node:

- Selecting a call row highlights its caller node, callee node, and corresponding diagram edge.
- Selecting a diagram edge selects the first call in the active phase that uses that edge. If no
  active-phase call uses the edge, it selects the first call in global sequence order that uses it.
- Selecting a node keeps the current source-backed node detail behavior.
- Changing phase highlights that phase's calls in the full timeline instead of hiding other phases.

The default selection is the first call in the first phase. This gives the user an immediate ordered
entry point instead of an empty diagram.

## Layout

Desktop layout:

- Top row: lifecycle subject switcher and phase tabs.
- Main content: diagram and call sequence in the primary area, with the detail drawer sticky on the
  right.
- The call sequence must be visible without opening the drawer because it is the primary teaching
  surface for this feature.

Mobile and narrow layout:

- Controls first.
- Call sequence before the diagram.
- Diagram after the sequence.
- Drawer last.

This order favors comprehension on small screens: read the ordered story first, then inspect the
spatial map and details.

## Data Model

Lifecycle manifests will require a `calls` array. Existing lifecycle data should be migrated rather
than supported through a long-term compatibility fallback.

`edges` continue to model topology: which components can communicate. `calls` model ordered events
in the walkthrough.

```ts
interface LifecycleCall {
  id: string
  phase_id: string
  seq: number
  from: string
  to: string
  edge_id: string
  kind:
    | 'rpc'
    | 'poll'
    | 'response'
    | 'activation'
    | 'command'
    | 'completion'
    | 'heartbeat'
    | 'history-event'
    | 'task-dispatch'
  message: string
  summary: string
  details: string[]
  payload?: string[]
  refs: SourceRef[]
}
```

Fields:

- `id`: stable identifier for selection, tests, and links.
- `phase_id`: phase that owns the call.
- `seq`: global lifecycle ordering number.
- `from` / `to`: caller and callee node ids for this ordered call.
- `edge_id`: topology edge used for diagram highlighting.
- `kind`: message category used for styling and filtering.
- `message`: short API, command, event, task, or payload name.
- `summary`: one-sentence explanation for the row.
- `details`: drawer-level explanation of what happens and why.
- `payload`: optional compact list of important fields, such as workflow id, task queue, commands,
  heartbeat details, or history event names.
- `refs`: source references directly relevant to the call.

The same topology edge may appear in multiple calls with different direction, kind, or message. For
example, a long poll request and its response should be represented as separate ordered calls.

## Required Happy-Path Calls

The initial migrated happy-path manifest should include at least these ordered calls:

1. Kilvin client -> Frontend: `StartWorkflowExecution`.
2. Frontend -> History: create execution and append `WorkflowExecutionStarted`.
3. History -> Matching: enqueue the first workflow task.
4. Python worker -> Bridge worker: `poll_workflow_activation`.
5. Bridge worker -> Core worker: bridge poll request.
6. Core worker -> Matching: `PollWorkflowTaskQueue`.
7. Matching -> Core worker: workflow task response.
8. Core worker -> Python activation: `WorkflowActivation`.
9. Python activation -> Core worker: workflow task completion with commands.
10. Core worker -> Frontend: `RespondWorkflowTaskCompleted`.
11. History -> Matching: enqueue activity task.
12. Core worker -> Matching: activity task poll.
13. Matching -> Core worker: activity task response.
14. Core worker -> Python activity task: activity invocation.
15. Python activity task -> Core worker: heartbeat.
16. Core worker -> Frontend: record heartbeat.
17. Python activity task -> Core worker: activity completion.
18. Core worker -> Frontend: activity completion response.
19. History -> Matching: enqueue follow-up workflow task.
20. Core worker -> Python activation: next workflow activation or completion turn.

Exact source-backed labels may be adjusted during implementation, but the sequence must preserve the
Temporal mechanics: workers poll for tasks, the server responds to polls, workflow code emits
commands, and durable history remains the source of truth.

## Diagram Behavior

The lifecycle diagram will be upgraded without making it responsible for ordering:

- Add SVG arrow markers for edge direction.
- Use selected-call direction for edges that are reused in both directions.
- Show visible labels for the selected edge and active phase edges.
- Make diagram edges selectable with pointer input. Keyboard users select calls through the call
  sequence rows, which are the accessible ordered representation of edges.
- Use distinct visual states for selected call, active phase, and inactive topology.

Highlight derivation should come from calls:

- Selected call: strongest highlight for `from`, `to`, and `edge_id`.
- Active phase: medium highlight for calls whose `phase_id` matches the selected phase.
- Other lifecycle calls: dim but visible.
- Nodes not referenced by any call in the phase stay selectable but visually secondary.

## Drawer Behavior

The detail drawer supports two selected item types:

- `LifecycleCall`: primary call details.
- `LifecycleNode`: existing node details.

For a selected call, the drawer shows:

- message name
- caller and callee
- kind
- phase
- summary
- details
- payload fields when present
- source refs
- current read/run/inspect guide panel for the phase

For a selected node, the drawer keeps the current node summary, notes, source refs, and guide panel.

The empty state should be rare because the first call is selected by default. If selection is cleared,
the drawer shows the current phase summary and tells the user to choose a call or node.

## Validation And Error Handling

Lifecycle manifests must be validated before rendering:

- every call `from` and `to` references an existing node
- every call `phase_id` references an existing phase
- every call `edge_id` references an existing edge
- every call `seq` is unique
- display order is ascending by `seq`
- every phase has at least one call
- each call's `edge_id` connects the same pair of nodes as `from` and `to`; reverse direction is
  allowed for response calls when the same topology edge represents both request and response
- every call has `message`, `summary`, and at least one `details` item
- source refs keep existing repo/path/line/url requirements

If a lifecycle manifest is invalid, the explorer should show a clear manifest error instead of
rendering a misleading partial visualization.

## Implementation Boundaries

- Keep the feature inside the existing `explorer/` app and lifecycle data model.
- Do not introduce runtime tracing or workflow execution.
- Do not build a separate sequence visualization mode; the sequence belongs in the current lifecycle
  deep dive.
- Do not keep a long-term fallback for lifecycle manifests without `calls`.
- Avoid unrelated visual redesign. The change should improve comprehension while preserving the
  current Temporal Explorer shell and source-backed walkthrough style.

## Testing And Acceptance

Tests should cover:

- manifest validation for valid calls and common broken references
- active phase derivation from calls
- selected call derivation of highlighted nodes and edge
- call row selection updating drawer content
- diagram edge selection updating selected call where unambiguous
- required `calls` handling for lifecycle manifests
- existing keyboard node selection behavior

Manual acceptance:

- A user can read the happy path top to bottom and understand who calls whom.
- Polling phases make it clear that workers call the server and the server responds to long polls.
- Commands and completions are distinguishable from direct RPCs.
- Selecting any timeline row visibly updates the diagram and drawer.
- The diagram still works as a spatial map of app, SDK, bridge, core, and server.
- Mobile layout preserves the sequence-first reading order.
