import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import LifecycleExplorer from './LifecycleExplorer'
import type { LifecycleManifest } from './types'

vi.mock('@/lib/fetch', () => ({
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  fetchExplorerJson: vi.fn(async (path: string) => {
    const data: Record<string, unknown> = {
      'lifecycle/index.json': [
        {
          slug: 'kilvin-asyncio-happy-path',
          label: 'Kilvin asyncio happy path',
          manifest: 'lifecycle/kilvin-asyncio-happy-path.json',
        },
      ],
      'lifecycle/kilvin-asyncio-happy-path.json': manifest,
    }
    const value = data[path]
    if (!value) throw new Error(`unexpected path ${path}`)
    return value
  }),
}))

const manifest: LifecycleManifest = {
  generated_at: '2026-05-31T00:00:00Z',
  slug: 'kilvin-asyncio-happy-path',
  label: 'Kilvin asyncio happy path',
  phases: [
    {
      id: 'start',
      label: 'Start workflow',
      summary: 'Kilvin submits a staged training run.',
      node_ids: ['kilvin-client'],
      guide_anchor: 'happy-path-start-workflow-to-first-activation',
      guide_title: '4. Happy path: start workflow to first activation',
      hack_script: 'hacks/002_lifecycle_manifest.py',
      hack_summary: 'Walk the Kilvin asyncio happy-path lifecycle manifest in phase order.',
    },
  ],
  nodes: [
    {
      id: 'kilvin-client',
      label: 'Kilvin client',
      layer: 'kilvin',
      kind: 'client',
      summary: 'Starts the workflow.',
      notes: 'Client start crosses Frontend.',
      refs: [],
    },
  ],
  edges: [],
}

describe('LifecycleExplorer', () => {
  it('renders phase guide and hack links', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Read / Run / Inspect')).toBeTruthy()
    })

    expect(screen.getByRole('link', { name: /4\. Happy path/ }).getAttribute('href')).toBe(
      '/HACKERS_GUIDE.md#happy-path-start-workflow-to-first-activation',
    )
    expect(screen.getByText('python hacks/002_lifecycle_manifest.py')).toBeTruthy()
    expect(
      screen.getByText('Walk the Kilvin asyncio happy-path lifecycle manifest in phase order.'),
    ).toBeTruthy()
  })
})
