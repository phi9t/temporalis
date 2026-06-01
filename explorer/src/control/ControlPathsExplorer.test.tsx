import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ControlPathsExplorer from './ControlPathsExplorer'
import type { ControlScenario, LifecycleManifest } from '@/lifecycle/types'

vi.mock('@/lib/fetch', () => ({
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  fetchExplorerJson: vi.fn(async (path: string) => {
    const data: Record<string, unknown> = {
      'lifecycle/kilvin-asyncio-happy-path.json': lifecycle,
      'control-paths/index.json': [
        { slug: 'pause-resume', label: 'Pause / resume', manifest: 'control-paths/pause-resume.json' },
      ],
      'control-paths/pause-resume.json': scenario,
    }

    const value = data[path]
    if (!value) throw new Error(`unexpected path ${path}`)
    return value
  }),
}))

const lifecycle: LifecycleManifest = {
  generated_at: '2026-05-31T00:00:00Z',
  slug: 'kilvin-asyncio-happy-path',
  label: 'Kilvin asyncio happy path',
  phases: [],
  nodes: [
    {
      id: 'workflow-activation',
      label: 'Activation',
      layer: 'sdk-python',
      kind: 'workflow',
      summary: 'Python resumes workflow code.',
      notes: 'Replay feeds deterministic activations back to Python.',
      refs: [
        {
          repo: 'sdk-python',
          label: '_handle_activation',
          path: 'temporalio/worker/_workflow.py',
          line: 244,
          symbol: '_handle_activation',
          url: 'https://github.com/temporalio/sdk-python/blob/main/temporalio/worker/_workflow.py',
        },
      ],
    },
    {
      id: 'history-service',
      label: 'History',
      layer: 'server',
      kind: 'history',
      summary: 'History stores workflow events.',
      notes: 'History is the source of truth for replay.',
      refs: [],
    },
  ],
  edges: [
    {
      id: 'workflow-complete',
      from: 'workflow-activation',
      to: 'history-service',
      kind: 'completion',
      label: 'RespondWorkflowTaskCompleted',
    },
  ],
  calls: [],
}

const scenario: ControlScenario = {
  slug: 'pause-resume',
  label: 'Pause / resume',
  summary: 'Signals change workflow state; replay preserves deterministic history.',
  highlight_node_ids: ['workflow-activation', 'history-service'],
  highlight_edge_ids: ['workflow-complete'],
  guide_anchor: 'pause-resume-as-signalupdate-driven-coordination',
  guide_title: '9. Pause/resume as signal/update-driven coordination',
  hack_script: 'hacks/005_control_paths.py',
  hack_summary: 'Print control-path overlays.',
  details: [
    'Python workflow code records pause state.',
    'History stores signal or update events.',
    'sdk-core replays history before the next activation.',
  ],
  steps: [
    {
      id: 'pause-resume-command',
      seq: 1,
      kind: 'completion',
      from: 'workflow-activation',
      to: 'history-service',
      edge_id: 'workflow-complete',
      message: 'RespondWorkflowTaskCompleted',
      summary: 'Python workflow code records pause state.',
      details: ['Python workflow code records pause state.'],
      affected_node_ids: ['workflow-activation', 'history-service'],
      affected_edge_ids: ['workflow-complete'],
    },
  ],
}

describe('ControlPathsExplorer', () => {
  it('loads control scenarios as lifecycle diagram overlays', async () => {
    render(<ControlPathsExplorer navigate={vi.fn()} />)

    expect(screen.getByText('Loading control paths...')).toBeTruthy()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Pause / resume' }).getAttribute('aria-pressed')).toBe('true')
    })

    expect(screen.getByText('Signals change workflow state; replay preserves deterministic history.')).toBeTruthy()
    expect(screen.getByRole('link', { name: /9\. Pause\/resume/ }).getAttribute('href')).toBe(
      '/HACKERS_GUIDE.md#pause-resume-as-signalupdate-driven-coordination',
    )
    expect(screen.getByText('python hacks/005_control_paths.py')).toBeTruthy()
    expect(screen.getByText('sdk-core replays history before the next activation.')).toBeTruthy()
    expect(screen.getByRole('group', { name: 'Temporal lifecycle diagram' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Activation' })).toBeTruthy()
  })
})
