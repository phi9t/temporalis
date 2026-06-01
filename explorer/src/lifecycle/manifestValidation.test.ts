import { describe, expect, it } from 'vitest'
import { getSortedLifecycleCalls, validateLifecycleManifest } from './manifestValidation'
import type { LifecycleManifest } from './types'

const baseManifest: LifecycleManifest = {
  generated_at: '2026-05-31T00:00:00Z',
  slug: 'test',
  label: 'Test manifest',
  phases: [
    {
      id: 'start',
      label: 'Start',
      summary: 'Start phase.',
      node_ids: ['app', 'server'],
      guide_anchor: 'start',
      guide_title: 'Start',
      hack_script: 'hacks/002_lifecycle_manifest.py',
      hack_summary: 'Run the lifecycle manifest hack.',
    },
  ],
  nodes: [
    {
      id: 'app',
      label: 'App',
      layer: 'kilvin',
      kind: 'client',
      summary: 'Starts work.',
      notes: 'Client code starts work.',
      refs: [],
    },
    {
      id: 'server',
      label: 'Server',
      layer: 'server',
      kind: 'service',
      summary: 'Accepts work.',
      notes: 'Server accepts work.',
      refs: [],
    },
  ],
  edges: [
    {
      id: 'app-server',
      from: 'app',
      to: 'server',
      kind: 'rpc',
      label: 'Start',
    },
  ],
  calls: [
    {
      id: 'start-rpc',
      phase_id: 'start',
      seq: 2,
      from: 'app',
      to: 'server',
      edge_id: 'app-server',
      kind: 'rpc',
      message: 'StartWorkflowExecution',
      summary: 'App starts a workflow.',
      details: ['The app sends a start request to the server frontend.'],
      refs: [],
    },
    {
      id: 'start-response',
      phase_id: 'start',
      seq: 1,
      from: 'server',
      to: 'app',
      edge_id: 'app-server',
      kind: 'response',
      message: 'Run id response',
      summary: 'Server returns the run id.',
      details: ['The response travels over the same topology edge in reverse.'],
      payload: ['run_id'],
      refs: [],
    },
  ],
}

describe('lifecycle manifest validation', () => {
  it('accepts a manifest with required calls and reverse response edges', () => {
    expect(() => validateLifecycleManifest(baseManifest)).not.toThrow()
  })

  it('sorts calls by global sequence number', () => {
    expect(getSortedLifecycleCalls(baseManifest).map((call) => call.id)).toEqual([
      'start-response',
      'start-rpc',
    ])
  })

  it('rejects manifests without calls', () => {
    const manifest = { ...baseManifest, calls: undefined } as unknown as LifecycleManifest

    expect(() => validateLifecycleManifest(manifest)).toThrow(
      'Lifecycle manifest test must include calls',
    )
  })

  it('rejects calls that reference missing nodes', () => {
    const manifest: LifecycleManifest = {
      ...baseManifest,
      calls: [
        {
          ...baseManifest.calls[0],
          to: 'missing-node',
        },
      ],
    }

    expect(() => validateLifecycleManifest(manifest)).toThrow(
      'Call start-rpc references missing to node missing-node',
    )
  })

  it('rejects calls whose edge does not connect the caller and callee', () => {
    const manifest: LifecycleManifest = {
      ...baseManifest,
      nodes: [
        ...baseManifest.nodes,
        {
          id: 'other',
          label: 'Other',
          layer: 'sdk-core',
          kind: 'worker',
          summary: 'Other node.',
          notes: 'Other node.',
          refs: [],
        },
      ],
      calls: [
        {
          ...baseManifest.calls[0],
          to: 'other',
        },
      ],
    }

    expect(() => validateLifecycleManifest(manifest)).toThrow(
      'Call start-rpc edge app-server does not connect app -> other',
    )
  })

  it('rejects duplicate sequence numbers', () => {
    const manifest: LifecycleManifest = {
      ...baseManifest,
      calls: [
        baseManifest.calls[0],
        {
          ...baseManifest.calls[1],
          seq: baseManifest.calls[0].seq,
        },
      ],
    }

    expect(() => validateLifecycleManifest(manifest)).toThrow('Duplicate lifecycle call seq 2')
  })
})
