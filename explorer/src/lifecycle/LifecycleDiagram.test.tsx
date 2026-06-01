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
