/* eslint-disable react-refresh/only-export-components */
import { cn } from '@/lib/utils'
import type { LifecycleCall, LifecycleEdge, LifecycleNode } from './types'

const EDGE_LABEL_MAX = 29
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

interface Rect {
  x: number
  y: number
  width: number
  height: number
}

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

function edgeMatchesCallDirection(edge: LifecycleEdge, from: string | null, to: string | null): from is string {
  if (!from || !to) return false

  return (edge.from === from && edge.to === to) || (edge.from === to && edge.to === from)
}

export function truncateEdgeLabel(label: string): string {
  if (label.length <= EDGE_LABEL_MAX) return label

  return `${label.slice(0, EDGE_LABEL_MAX - 3)}...`
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function overlapArea(a: Rect, b: Rect): number {
  const xOverlap = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x))
  const yOverlap = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y))

  return xOverlap * yOverlap
}

function rectOverlapsAny(rect: Rect, blockedRects: Rect[]): boolean {
  return blockedRects.some((blockedRect) => overlapArea(rect, blockedRect) > 0)
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
  blockedRects = [],
}: {
  x1: number
  y1: number
  x2: number
  y2: number
  labelWidth: number
  labelHeight: number
  viewBoxWidth: number
  viewBoxHeight: number
  blockedRects?: Rect[]
}) {
  const midX = (x1 + x2) / 2
  const midY = (y1 + y2) / 2
  const mostlyVertical = Math.abs(y2 - y1) > Math.abs(x2 - x1) * 1.25
  const verticalY = midY - labelHeight / 2
  const horizontalX = midX - labelWidth / 2
  const horizontalAboveY = midY - labelHeight - 12
  const placeAt = (rawX: number, rawY: number) => ({
    x: Math.round(clamp(rawX, 8, viewBoxWidth - labelWidth - 8)),
    y: Math.round(clamp(rawY, 8, viewBoxHeight - labelHeight - 8)),
  })

  if (blockedRects.length > 0) {
    const candidates = mostlyVertical
      ? [placeAt(midX + 18, verticalY), placeAt(midX - labelWidth - 18, verticalY)]
      : [
          placeAt(horizontalX, horizontalAboveY),
          placeAt(horizontalX, midY + 12),
          placeAt(horizontalX, horizontalAboveY - 30),
          placeAt(horizontalX, midY + 42),
          placeAt(midX + 18, verticalY),
          placeAt(midX - labelWidth - 18, verticalY),
        ]
    const openCandidate = candidates.find((candidate) => {
      return !rectOverlapsAny({ ...candidate, width: labelWidth, height: labelHeight }, blockedRects)
    })

    if (openCandidate) return openCandidate

    const [best] = candidates
      .map((candidate, index) => ({
        ...candidate,
        index,
        blockedArea: blockedRects.reduce(
          (total, rect) => total + overlapArea({ ...candidate, width: labelWidth, height: labelHeight }, rect),
          0,
        ),
      }))
      .sort((a, b) => a.blockedArea - b.blockedArea || a.index - b.index)

    return { x: best.x, y: best.y }
  }

  return mostlyVertical ? placeAt(midX + 18, verticalY) : placeAt(horizontalX, horizontalAboveY)
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

export default function LifecycleDiagram({
  nodes,
  edges,
  activeNodeIds,
  activeEdgeIds,
  selectedId,
  selectedEdgeId = null,
  selectedCallFrom = null,
  selectedCallTo = null,
  selectedCall = null,
  activeCallLabels = [],
  activePhaseId = '',
  selectedEndpointNodeIds = new Set<string>(),
  onSelect,
  onSelectEdge,
}: {
  nodes: LifecycleNode[]
  edges: LifecycleEdge[]
  activeNodeIds: Set<string>
  activeEdgeIds: Set<string>
  selectedId: string | null
  selectedEdgeId?: string | null
  selectedCallFrom?: string | null
  selectedCallTo?: string | null
  selectedCall?: LifecycleCall | null
  activeCallLabels?: LifecycleCall[]
  activePhaseId?: string
  selectedEndpointNodeIds?: Set<string>
  onSelect: (node: LifecycleNode) => void
  onSelectEdge?: (edgeId: string) => void
}) {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const blockedRects = nodes.map(nodeBox)

  return (
    <svg viewBox="0 0 820 560" className="lifecycle-svg" role="group" aria-label="Temporal lifecycle diagram">
      <defs>
        <marker id="lifecycle-arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" />
        </marker>
        <marker
          id="lifecycle-arrow-active"
          viewBox="0 0 10 10"
          refX="8.5"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" />
        </marker>
        <marker
          id="lifecycle-arrow-selected"
          viewBox="0 0 10 10"
          refX="8.5"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" />
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

        const active = activeEdgeIds.has(edge.id)
        const selected = selectedEdgeId === edge.id
        const directedFrom =
          selected && edgeMatchesCallDirection(edge, selectedCallFrom, selectedCallTo)
            ? byId.get(selectedCallFrom)
            : from
        const directedTo =
          selected && edgeMatchesCallDirection(edge, selectedCallFrom, selectedCallTo)
            ? byId.get(selectedCallTo ?? '')
            : to

        if (!directedFrom || !directedTo) return null

        const a = nodeBox(directedFrom)
        const b = nodeBox(directedTo)
        const marker = selected ? 'url(#lifecycle-arrow-selected)' : active ? 'url(#lifecycle-arrow-active)' : 'url(#lifecycle-arrow)'
        const selectable = Boolean(onSelectEdge)
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
                blockedRects,
              })
            : null

        function selectEdge() {
          onSelectEdge?.(edge.id)
        }

        return (
          <g
            key={edge.id}
            className={cn('lifecycle-edge', active && 'active', selected && 'selected', selectable && 'selectable')}
            role={selectable ? 'button' : undefined}
            tabIndex={selectable ? 0 : undefined}
            aria-label={selectable ? `Diagram edge ${label?.fullText ?? edge.label}` : undefined}
            aria-pressed={selectable ? selected : undefined}
            onClick={selectEdge}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                selectEdge()
              }
            }}
          >
            <line className="lifecycle-edge-hit" x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} />
            <line className="lifecycle-edge-line" x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} markerEnd={marker} />
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
            <title>{edge.label}</title>
          </g>
        )
      })}

      {nodes.map((node) => {
        const box = nodeBox(node)
        const active = activeNodeIds.has(node.id)
        const selected = selectedId === node.id
        const selectedEndpoint = selectedEndpointNodeIds.has(node.id)

        return (
          <g
            key={node.id}
            className={cn('lifecycle-node', active && 'active', selectedEndpoint && 'selected-endpoint', selected && 'selected')}
            transform={`translate(${box.x},${box.y})`}
            role="button"
            tabIndex={0}
            aria-label={node.label}
            onClick={() => onSelect(node)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onSelect(node)
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
