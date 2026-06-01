# Control Paths Sticky Sequence And Diagram Design

## Summary

Upgrade Control Paths from a prose overlay into a sequence-driven visualization. Each scenario should
read as an ordered causal path through app, SDK, core, and server responsibilities, while the diagram
stays visible and explains the selected message with the same polished edge rendering criteria used
by the lifecycle explorer.

This is an interaction and rendering upgrade. It adds optional structured control-step data to
control scenario manifests, but it does not change the base lifecycle topology or Temporal
semantics.

## Recommended Approach

Use **scenario sequence + sticky diagram** as the primary design.

Control scenarios should expose ordered steps where available. Each step represents one meaningful
control-path action: a signal, update, retry decision, replay activation, heartbeat cancellation,
sticky-cache miss, or related control transition. The existing `details` prose can remain as summary
copy and as an initial fallback when a scenario does not yet have structured steps.

This keeps Control Paths consistent with Lifecycle Deep Dive while giving advanced scenarios their
own causal story instead of only highlighting static nodes and edges.

## Page Architecture

The page keeps the existing scenario selector, scenario summary, guide link, hack command, and guide
metadata. The main scenario card becomes a coordinated workspace:

- `control-sequence`: ordered scenario steps.
- `lifecycle-diagram`: reused topology diagram with selected control-step emphasis.
- `lifecycle-drawer-shell`: sticky detail drawer for the selected node or selected control step.

Desktop layout:

- Sequence and diagram sit side by side inside the main card.
- The sequence panel scrolls independently with a viewport-relative max height.
- The diagram remains sticky and visible while the sequence scrolls.
- The drawer remains sticky at the right.

Mobile layout:

- Avoid nested scrolling.
- Preserve natural page flow: selector, summary, sequence, diagram, drawer.
- Put sequence before diagram so the causal story is read before the map is inspected.

## Control Step Model

Each structured control step should support:

- stable `id`
- `from` node id where a caller/source exists
- `to` node id where a callee/target exists
- `edge_id` when the step corresponds to a lifecycle topology edge
- `message` for the visible call, operation, or control transition
- `summary` for the row and drawer
- optional `detail` for deeper explanation
- optional `affected_node_ids`
- optional `affected_edge_ids`

The model should tolerate control-only steps that do not map perfectly to one topology edge. In that
case the step can still select affected nodes and edges, while the diagram avoids inventing a fake
direct call.

Existing scenario fields remain valid:

- `highlight_node_ids` and `highlight_edge_ids` define the scenario-wide context.
- `details` remains the prose explanation.
- guide and hack metadata remain unchanged.

If `steps` is absent, the UI may derive coarse read-only steps from `details`, but those fallback
steps should not pretend to have precise caller/callee semantics.

## Component And State Design

`ControlPathsExplorer` owns:

- lifecycle manifest loading
- control index loading
- selected scenario loading
- selected step/node state
- normalized `controlSteps`
- active scenario node and edge sets
- row registration for scroll reveal

`ControlSequence` renders:

- ordered step rows
- source and target labels when known
- message text
- selected state
- row refs for scroll reveal

`LifecycleDiagram` remains shared:

- selected control steps should pass call-like selected-edge data into the existing selected edge
  rendering path
- scenario steps can provide active labels where precise messages are known
- diagram edge selection should call back with the selected edge id

`LifecycleDrawer` should continue showing node details and should also support selected control-step
details. The drawer should make the selected step's message, source, target, and explanation clear.

The core state rule is: **one selected control step drives sequence highlight, diagram highlight, and
drawer detail**.

## Interaction Model

Desktop behavior:

- Selecting a sequence row updates diagram emphasis and drawer content.
- Selecting a diagram edge selects the nearest matching control step and scrolls that row into view.
- Changing scenarios resets selection to the first meaningful scenario step.
- Scrolling the sequence does not change selection by itself.

Mobile and narrow behavior:

- Sequence rows remain normal page content.
- Diagram follows the sequence.
- No internal sequence scroll is used.

Keyboard behavior:

- Step rows are focusable buttons.
- Edge selection may scroll the selected step into view, but should not steal focus unless focus is
  already inside the sequence panel.
- No auto-select-on-scroll in this version.

## Rendering Criteria

The diagram should follow the lifecycle aesthetic and beauty standard:

- The selected control step must be legible in the diagram in under one second.
- Selected path clarity wins over contextual labels.
- Scenario context remains quiet and restrained.
- Unrelated topology recedes enough to orient without competing.
- Edges are crisp, intentional, and balanced.
- Labels look attached to edges, not pasted onto the SVG.
- Badge size, padding, and radius are modest.
- Contrast is strong for selected state and subdued for active context.
- The diagram should feel like a polished technical instrument, not a debug overlay.

Selected step rendering:

- Use the selected step `message` for the edge label.
- Use the selected step `from -> to` direction when both endpoints are known.
- Support reverse-direction control steps such as replay or response-like transitions.
- Highlight endpoint nodes for the selected step.
- Preserve selected labels even when space is tight.

Active scenario rendering:

- Use scenario step messages for active labels only when they add clarity.
- Limit active labels to avoid visual chatter.
- Hide active labels when they would collide with selected labels, nodes, or each other.
- Fall back to topology labels only when no precise step message exists.

Label placement:

- Compute placement from the rendered edge direction.
- Prefer the edge midpoint with a clear offset.
- Place mostly vertical labels to the side.
- Place mostly horizontal or diagonal labels above the edge.
- Clamp labels inside the SVG viewbox.
- Avoid node overlap.
- Avoid selected-label overlap.
- Truncate visible text around the same length as lifecycle labels, preserving full text through
  accessible labels or titles.

## Data Flow

1. Load `lifecycle/kilvin-asyncio-happy-path.json`.
2. Load `control-paths/index.json`.
3. Load the selected scenario manifest.
4. Normalize the scenario into `controlSteps`.
5. Pick the first meaningful step as the default selection.
6. Render sequence, diagram, and drawer from the same selected state.
7. When a diagram edge is selected, find the nearest matching structured step for that edge and
   scroll its row into view.

## Implementation Boundaries

- Keep the lifecycle topology schema stable.
- Prefer additive control scenario data over changing existing fields.
- Reuse `LifecycleDiagram` rather than forking diagram rendering.
- Reuse the lifecycle sequence interaction rules where possible.
- Do not add scroll-driven auto-selection.
- Do not require animation for comprehension.
- Respect reduced-motion preferences if smooth scrolling is used.

## Testing And Acceptance

Automated tests should cover:

- control scenarios render an ordered sequence panel
- default selection chooses the first control step
- selecting a sequence row updates diagram selected edge label and drawer detail
- selecting a diagram edge selects the nearest matching control step
- edge selection scrolls the matching step into view
- scrolling the control sequence does not change selection
- scenario changes reset to the first meaningful step
- selected labels use control step messages
- fallback detail-derived steps do not claim precise source/target semantics
- long labels truncate while preserving full accessible text
- active labels remain bounded and do not overlap nodes or selected labels

Manual acceptance:

- On desktop, the diagram stays visible while reading a long control sequence.
- On mobile, there is no nested scrolling.
- The selected control step is visually obvious.
- The path reads as caller -> callee -> message when structured data exists.
- Pause/resume, retry, replay, cancellation, and sticky-cache scenarios each explain what changes
  from the happy path.
- The diagram remains composed: clean spacing, crisp edges, restrained contrast, readable labels,
  and no clutter.
