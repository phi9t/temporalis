import type { LifecycleCall, LifecycleEdge, LifecycleManifest } from './types'

function requireText(value: string, message: string) {
  if (value.trim().length === 0) throw new Error(message)
}

function edgeConnects(edge: LifecycleEdge, from: string, to: string, kind: string): boolean {
  if (edge.from === from && edge.to === to) return true
  return kind === 'response' && edge.from === to && edge.to === from
}

export function validateLifecycleManifest(manifest: LifecycleManifest): void {
  if (!Array.isArray(manifest.calls) || manifest.calls.length === 0) {
    throw new Error(`Lifecycle manifest ${manifest.slug} must include calls`)
  }

  const phases = new Set(manifest.phases.map((phase) => phase.id))
  const nodes = new Set(manifest.nodes.map((node) => node.id))
  const edges = new Map(manifest.edges.map((edge) => [edge.id, edge]))
  const seqs = new Set<number>()
  const callCountByPhase = new Map(manifest.phases.map((phase) => [phase.id, 0]))

  for (const call of manifest.calls) {
    requireText(call.id, 'Lifecycle call id must not be empty')
    requireText(call.message, `Call ${call.id} must include message`)
    requireText(call.summary, `Call ${call.id} must include summary`)

    if (!Array.isArray(call.details) || call.details.length === 0) {
      throw new Error(`Call ${call.id} must include details`)
    }

    for (const detail of call.details) {
      requireText(detail, `Call ${call.id} detail must not be empty`)
    }

    if (!phases.has(call.phase_id)) {
      throw new Error(`Call ${call.id} references missing phase ${call.phase_id}`)
    }

    if (!nodes.has(call.from)) {
      throw new Error(`Call ${call.id} references missing from node ${call.from}`)
    }

    if (!nodes.has(call.to)) {
      throw new Error(`Call ${call.id} references missing to node ${call.to}`)
    }

    const edge = edges.get(call.edge_id)
    if (!edge) {
      throw new Error(`Call ${call.id} references missing edge ${call.edge_id}`)
    }

    if (!edgeConnects(edge, call.from, call.to, call.kind)) {
      throw new Error(`Call ${call.id} edge ${call.edge_id} does not connect ${call.from} -> ${call.to}`)
    }

    if (seqs.has(call.seq)) {
      throw new Error(`Duplicate lifecycle call seq ${call.seq}`)
    }
    seqs.add(call.seq)

    callCountByPhase.set(call.phase_id, (callCountByPhase.get(call.phase_id) ?? 0) + 1)
  }

  for (const phase of manifest.phases) {
    if ((callCountByPhase.get(phase.id) ?? 0) === 0) {
      throw new Error(`Lifecycle phase ${phase.id} must include at least one call`)
    }
  }
}

export function getSortedLifecycleCalls(manifest: LifecycleManifest): LifecycleCall[] {
  validateLifecycleManifest(manifest)
  return [...manifest.calls].sort((a, b) => a.seq - b.seq)
}
