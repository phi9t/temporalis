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
  selectedId,
  selectedEdgeId = null,
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
  selectedEndpointNodeIds?: Set<string>
  onSelect: (node: LifecycleNode) => void
  onSelectEdge?: (edgeId: string) => void
}) {
  const byId = new Map(nodes.map((node) => [node.id, node]))

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

        const a = nodeBox(from)
        const b = nodeBox(to)
        const active = activeEdgeIds.has(edge.id)
        const selected = selectedEdgeId === edge.id
        const labelX = (a.cx + b.cx) / 2
        const labelY = (a.cy + b.cy) / 2 - 8
        const marker = selected ? 'url(#lifecycle-arrow-selected)' : active ? 'url(#lifecycle-arrow-active)' : 'url(#lifecycle-arrow)'

        return (
          <g
            key={edge.id}
            className={cn('lifecycle-edge', active && 'active', selected && 'selected', onSelectEdge && 'selectable')}
            onClick={() => onSelectEdge?.(edge.id)}
          >
            <line className="lifecycle-edge-hit" x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} />
            <line className="lifecycle-edge-line" x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} markerEnd={marker} />
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
