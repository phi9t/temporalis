export type LayerId = 'kilvin' | 'sdk-python' | 'bridge' | 'sdk-core' | 'server'

export type LifecycleCallKind =
  | 'rpc'
  | 'poll'
  | 'response'
  | 'activation'
  | 'command'
  | 'completion'
  | 'heartbeat'
  | 'history-event'
  | 'task-dispatch'

export type ControlStepKind = LifecycleCallKind | 'signal' | 'failure' | 'timer' | 'cache'

export interface SourceRef {
  repo: string
  ref?: string
  label: string
  path: string
  line: number
  symbol: string
  url: string
}

export interface LifecycleNode {
  id: string
  label: string
  layer: LayerId
  kind: string
  summary: string
  notes: string
  refs: SourceRef[]
}

export interface LifecycleEdge {
  id: string
  from: string
  to: string
  kind: string
  label: string
}

export interface LifecycleCall {
  id: string
  phase_id: string
  seq: number
  from: string
  to: string
  edge_id: string
  kind: LifecycleCallKind
  message: string
  summary: string
  details: string[]
  payload?: string[]
  refs: SourceRef[]
}

export type LifecycleSelection =
  | { type: 'call'; call: LifecycleCall }
  | { type: 'node'; node: LifecycleNode }

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

export interface GuideHackLink {
  guide_anchor: string
  guide_title: string
  hack_script: string
  hack_summary: string
}

export interface LifecyclePhase extends GuideHackLink {
  id: string
  label: string
  summary: string
  node_ids: string[]
}

export interface LifecycleManifest {
  generated_at: string
  slug: string
  label: string
  phases: LifecyclePhase[]
  nodes: LifecycleNode[]
  edges: LifecycleEdge[]
  calls: LifecycleCall[]
}

export interface ControlScenario extends GuideHackLink {
  slug: string
  label: string
  summary: string
  details: string[]
  highlight_node_ids: string[]
  highlight_edge_ids: string[]
  steps?: ControlStep[]
}
