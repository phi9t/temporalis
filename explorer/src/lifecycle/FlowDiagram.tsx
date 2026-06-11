import type { ControlStep, LifecycleCall, LifecycleNode } from './types'

type FlowGroupId = 'user-app' | 'worker' | 'server'

interface FlowGroup {
  id: FlowGroupId
  label: string
  nodeIds: string[]
}

export interface FlowItem<TSource = unknown> {
  id: string
  seq: number
  from: string
  to: string
  kind: string
  message: string
  summary: string
  source: TSource
}

interface FlowDiagramProps<TSource> {
  items: FlowItem<TSource>[]
  nodes: LifecycleNode[]
  selectedItemId: string | null
  activeNodeIds: Set<string>
  selectedNodeId: string | null
  onSelectItem: (item: FlowItem<TSource>) => void
  onSelectNode: (node: LifecycleNode) => void
}

const FLOW_GROUPS: FlowGroup[] = [
  {
    id: 'user-app',
    label: 'User app',
    nodeIds: ['kilvin-client'],
  },
  {
    id: 'worker',
    label: 'Worker',
    nodeIds: [
      'python-worker',
      'workflow-activation',
      'activity-task',
      'bridge-worker',
      'core-runtime',
      'core-worker',
    ],
  },
  {
    id: 'server',
    label: 'Temporal server',
    nodeIds: ['frontend-service', 'history-service', 'matching-service'],
  },
]

const LAYER_LABELS: Record<LifecycleNode['layer'], string> = {
  kilvin: 'User app',
  'sdk-python': 'Python SDK',
  bridge: 'Bridge',
  'sdk-core': 'sdk-core',
  server: 'Server',
}

export function lifecycleCallToFlowItem(call: LifecycleCall): FlowItem<LifecycleCall> {
  return {
    id: call.id,
    seq: call.seq,
    from: call.from,
    to: call.to,
    kind: call.kind,
    message: call.message,
    summary: call.summary,
    source: call,
  }
}

export function controlStepToFlowItem(step: ControlStep): FlowItem<ControlStep> | null {
  if (!step.from || !step.to) return null

  return {
    id: step.id,
    seq: step.seq,
    from: step.from,
    to: step.to,
    kind: step.kind,
    message: step.message,
    summary: step.summary,
    source: step,
  }
}

function padSequence(seq: number) {
  return String(seq).padStart(2, '0')
}

function groupForNode(nodeId: string): FlowGroupId | null {
  for (const group of FLOW_GROUPS) {
    if (group.nodeIds.includes(nodeId)) return group.id
  }

  return null
}

function nodeLabel(nodeId: string, nodesById: Map<string, LifecycleNode>) {
  return nodesById.get(nodeId)?.label ?? nodeId
}

export default function FlowDiagram<TSource>({
  items,
  nodes,
  selectedItemId,
  activeNodeIds,
  selectedNodeId,
  onSelectItem,
  onSelectNode,
}: FlowDiagramProps<TSource>) {
  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  const columnCount = Math.max(items.length, 1)

  return (
    <section className="flow-diagram" role="group" aria-label="Temporal swimlane flow diagram">
      <div className="flow-diagram-scroll">
        <div
          className="flow-grid"
          style={{ gridTemplateColumns: `minmax(260px, 320px) repeat(${columnCount}, minmax(220px, 260px))` }}
        >
          {FLOW_GROUPS.map((group) => {
            const groupNodes = group.nodeIds.map((nodeId) => nodesById.get(nodeId)).filter(Boolean) as LifecycleNode[]

            return (
              <div className={`flow-row flow-row--${group.id}`} key={group.id} role="row">
                <div className="flow-group-cell" role="rowheader">
                  <div className="flow-group-title">{group.label}</div>
                  <div className="flow-component-list">
                    {groupNodes.map((node) => {
                      const isSelected = selectedNodeId === node.id
                      const isActive = activeNodeIds.has(node.id)

                      return (
                        <button
                          className={[
                            'flow-component-chip',
                            isActive ? 'active' : '',
                            isSelected ? 'selected' : '',
                          ]
                            .filter(Boolean)
                            .join(' ')}
                          type="button"
                          key={node.id}
                          aria-label={node.label}
                          aria-pressed={isSelected}
                          onClick={() => onSelectNode(node)}
                        >
                          <span className="flow-component-layer">{LAYER_LABELS[node.layer]}</span>
                          <span>{node.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
                {items.length === 0 ? (
                  <div className="flow-empty-cell">No flow items for this selection.</div>
                ) : (
                  items.map((item) => {
                    const fromGroup = groupForNode(item.from)
                    const toGroup = groupForNode(item.to)
                    const isSource = fromGroup === group.id
                    const isTarget = toGroup === group.id
                    const isSelected = selectedItemId === item.id
                    const fromLabel = nodeLabel(item.from, nodesById)
                    const toLabel = nodeLabel(item.to, nodesById)

                    return (
                      <div className="flow-step-cell" key={`${group.id}-${item.id}`} role="cell">
                        {isSource ? (
                          <button
                            className={`flow-step-card${isSelected ? ' selected' : ''}`}
                            type="button"
                            aria-label={`Flow step ${padSequence(item.seq)} ${fromLabel} to ${toLabel} ${item.message}`}
                            aria-pressed={isSelected}
                            onClick={() => onSelectItem(item)}
                          >
                            <div className="flow-step-kicker">
                              <span>{padSequence(item.seq)}</span>
                              <span className="flow-kind">{item.kind}</span>
                            </div>
                            <div className="flow-step-message">{item.message}</div>
                            <div className="flow-step-route">
                              <span>{fromLabel}</span>
                              <span aria-hidden="true">→</span>
                              <span>{toLabel}</span>
                            </div>
                            <p>{item.summary}</p>
                          </button>
                        ) : null}
                        {!isSource && isTarget ? (
                          <div className={`flow-step-target${isSelected ? ' selected' : ''}`}>
                            <span>{padSequence(item.seq)}</span>
                            <span>arrives at {toLabel}</span>
                          </div>
                        ) : null}
                      </div>
                    )
                  })
                )}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
