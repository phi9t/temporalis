# Lifecycle Sticky Sequence And Diagram Edge Design

## Summary

Improve the lifecycle explorer so the call sequence and diagram stay cognitively linked while the
user reads through a long call list. The diagram should remain visible on desktop while the call
sequence scrolls independently, and diagram edges should render with clearer, more beautiful labels
that explain the selected call before the user opens the drawer.

This is an interaction and rendering upgrade. It does not change the lifecycle manifest data model or
Temporal call semantics.

## Interaction Model

Use **sticky diagram + scrollable call sequence** as the primary behavior.

Desktop behavior:

- The diagram remains visible while the user scrolls inside the call sequence panel.
- The call sequence panel has a bounded height based on viewport height.
- Selecting a call updates the diagram and drawer using the existing selected-call state.
- Selecting a diagram edge or changing phase scrolls the selected call row into view inside the
  sequence panel.
- Scrolling the call sequence does not change selection by itself.

Mobile and narrow behavior:

- Preserve the existing sequence-before-diagram page flow.
- Do not use nested scrolling on mobile.
- Let the page scroll naturally through controls, sequence, diagram, and drawer.

Keyboard behavior:

- Call rows remain normal focusable buttons.
- Edge and phase selection may scroll the selected call row into view, but should not steal focus
  unless the user is already interacting inside the call sequence.
- No auto-select-on-scroll in this version.

## Layout Rules

The lifecycle card contains two coordinated panels:

- `lifecycle-sequence`: the call sequence panel.
- `lifecycle-diagram`: the SVG diagram panel.

Desktop layout:

- Diagram and sequence remain side-by-side.
- The diagram panel is sticky within the viewport.
- The sequence panel scrolls independently with a viewport-relative max height.
- The drawer remains sticky at the right as it does today.

Mobile layout:

- Sequence appears before diagram in document order.
- Sequence panel uses natural height with no internal scroll.
- Diagram follows the sequence.

The selected call should remain discoverable in the sequence panel. When selection changes from a
phase tab or diagram edge, the UI scrolls the selected row into view with `block: nearest` behavior.

## Edge Rendering Priority

The diagram should feel like a polished technical instrument, not a debug SVG. The visual hierarchy is:

1. **Selected call**: the visual anchor.
2. **Active phase**: supporting context.
3. **Inactive topology**: quiet background structure.

If these compete, selected-call clarity wins.

## Selected Edge Rendering

The selected edge represents the exact selected call.

Render:

- high-contrast line
- clear arrowhead
- selected endpoint nodes
- label badge near the rendered edge
- label text from the selected call `message`

Direction:

- Use selected call `from -> to`, not the topology edge direction.
- This is required for response calls that reuse a topology edge in reverse.

Aesthetic standard:

- The selected edge should be obvious in under one second.
- The line should be crisp and restrained, not noisy.
- The label badge should look attached to the edge.
- Badge padding should be tight and visually balanced.
- The selected call should teach before the drawer is read.

## Active Edge Rendering

Active phase edges provide context around the selected call.

Render:

- medium-contrast line
- subtler arrowhead
- label badges only when they add clarity
- no more than 3-5 active labels visible at once

Label text:

- Use the current phase call message for that edge.
- If multiple current-phase calls share the edge, prefer the call nearest the selected call in
  sequence.
- Fall back to topology edge label only when no call message is available.

Aesthetic standard:

- Active labels must not create visual chatter.
- Active phase should read as a quiet network around the selected call.
- If a label causes clutter, hide the active label instead of forcing it.

## Inactive Edge Rendering

Inactive edges preserve map context.

Render:

- low-contrast line
- subdued arrowhead
- no visible label

Aesthetic standard:

- Inactive topology should orient the user without competing.
- Opacity should be low enough that active paths have room to breathe.

## Label Badge Placement

For every visible label:

- Compute placement from the rendered edge direction.
- Place labels near the midpoint of the rendered edge.
- For mostly vertical edges, place the label to the side of the midpoint.
- For mostly horizontal or diagonal edges, place the label above the midpoint.
- Apply a minimum offset so the label does not sit directly on the line.
- Draw a rounded background rect behind the text.
- Clamp the label origin so the full badge remains inside the SVG viewbox.
- Avoid node overlap.

Selected labels are preserved even when space is tight. Active labels may be hidden when cramped.

## Label Badge Styling

Badges should:

- use modest rounded rects
- have dark translucent fill
- have a subtle border or shadow for separation
- use the explorer monospace font
- avoid oversized pill shapes
- fit text with a fixed maximum width
- keep text optically centered

Visible label text should be truncated around 26-32 characters. Full text remains available through
`<title>` and accessible labels.

## Implementation Boundaries

- Keep changes inside the lifecycle explorer UI and CSS.
- Do not change lifecycle manifest schema or generator semantics.
- Do not add scroll-driven auto-selection.
- Do not add animation that is required for comprehension.
- Respect reduced-motion preferences if smooth scrolling is used.

## Testing And Acceptance

Automated tests should cover:

- selecting a phase scrolls the first call in that phase into the sequence viewport
- selecting a diagram edge scrolls the selected call row into the sequence viewport
- scroll alignment does not change selected call merely because the sequence scrolls
- selected edge label uses selected call `message`
- selected response calls use selected call direction and label text
- active edge labels use current-phase call messages where available
- long visible labels are truncated while full text remains accessible

Manual acceptance:

- On desktop, the diagram remains visible while the call sequence scrolls.
- On mobile, the sequence remains in normal page flow before the diagram.
- The selected call is immediately readable in the diagram.
- Labels do not collide with nodes in the happy-path manifest.
- There is no label soup.
- The diagram feels precise, restrained, and intentionally composed.
