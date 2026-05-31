export type LayerId = 'kilvin' | 'sdk-python' | 'bridge' | 'sdk-core' | 'server'

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
}

export interface ControlScenario extends GuideHackLink {
  slug: string
  label: string
  summary: string
  details: string[]
  highlight_node_ids: string[]
  highlight_edge_ids: string[]
}
