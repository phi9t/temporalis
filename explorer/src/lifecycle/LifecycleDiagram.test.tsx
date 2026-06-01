import { describe, expect, it } from 'vitest'
import {
  displayEdgeLabel,
  edgeLabelPlacement,
  planEdgeLabelPlacements,
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

function rectsOverlap(
  a: { x: number; y: number; width: number; height: number },
  b: { x: number; y: number; width: number; height: number },
) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y
}

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

  it('places mostly vertical labels away from blocked node rectangles', () => {
    const labelWidth = Math.round('StartWorkflowExecution'.length * 6.5 + 16)
    const labelHeight = 24
    const placement = edgeLabelPlacement({
      x1: 142,
      y1: 83,
      x2: 136,
      y2: 483,
      labelWidth,
      labelHeight,
      viewBoxWidth: 820,
      viewBoxHeight: 560,
      blockedRects: [{ x: 250, y: 258, width: 132, height: 50 }],
    })

    expect(
      rectsOverlap(
        { x: placement.x, y: placement.y, width: labelWidth, height: labelHeight },
        { x: 250, y: 258, width: 132, height: 50 },
      ),
    ).toBe(false)
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

  it('places horizontal server-layer labels away from blocked node rectangles', () => {
    const labelWidth = Math.round('WorkflowExecutionStarted'.length * 6.5 + 16)
    const labelHeight = 24
    const blockedRect = { x: 250, y: 458, width: 132, height: 50 }
    const placement = edgeLabelPlacement({
      x1: 136,
      y1: 483,
      x2: 316,
      y2: 483,
      labelWidth,
      labelHeight,
      viewBoxWidth: 820,
      viewBoxHeight: 560,
      blockedRects: [blockedRect],
    })

    expect(rectsOverlap({ x: placement.x, y: placement.y, width: labelWidth, height: labelHeight }, blockedRect)).toBe(
      false,
    )
  })

  it('plans selected labels before active labels so active badges do not overlap shared endpoints', () => {
    const labelHeight = 24
    const labels = planEdgeLabelPlacements({
      labels: [
        {
          edgeId: 'activity-command',
          text: 'ScheduleActivityTask',
          selected: false,
          x1: 316,
          y1: 383,
          x2: 676,
          y2: 383,
          labelWidth: 140,
          labelHeight,
        },
        {
          edgeId: 'frontend-history',
          text: 'ScheduleActivityTask',
          selected: true,
          x1: 136,
          y1: 483,
          x2: 316,
          y2: 483,
          labelWidth: 140,
          labelHeight,
        },
      ],
      blockedRects: [],
      viewBoxWidth: 820,
      viewBoxHeight: 560,
    })

    expect(labels.get('frontend-history')).toMatchObject({ visible: true, selected: true, x: 156, y: 447 })
    expect(labels.get('activity-command')?.visible).toBe(true)

    const selected = labels.get('frontend-history')
    const active = labels.get('activity-command')
    if (!selected || !active) throw new Error('expected both labels to be planned')

    expect(
      rectsOverlap(
        { x: selected.x, y: selected.y, width: selected.labelWidth, height: selected.labelHeight },
        { x: active.x, y: active.y, width: active.labelWidth, height: active.labelHeight },
      ),
    ).toBe(false)
  })

  it('hides active labels when every placement overlaps existing label or node rectangles', () => {
    const labelHeight = 24
    const labels = planEdgeLabelPlacements({
      labels: [
        {
          edgeId: 'activity-poll',
          text: 'PollActivityTaskQueue',
          selected: true,
          x1: 250,
          y1: 90,
          x2: 250,
          y2: 480,
          labelWidth: 140,
          labelHeight,
        },
        {
          edgeId: 'heartbeat',
          text: 'RecordActivityTaskHeartbeat',
          selected: false,
          x1: 250,
          y1: 90,
          x2: 250,
          y2: 480,
          labelWidth: 140,
          labelHeight,
        },
      ],
      blockedRects: [{ x: 92, y: 273, width: 140, height: labelHeight }],
      viewBoxWidth: 820,
      viewBoxHeight: 560,
    })

    expect(labels.get('activity-poll')?.visible).toBe(true)
    expect(labels.get('heartbeat')?.visible).toBe(false)
  })
})
