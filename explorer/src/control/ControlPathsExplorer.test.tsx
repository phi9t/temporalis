import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
      id: 'kilvin-client',
      label: 'Kilvin client',
      layer: 'kilvin',
      kind: 'client',
      summary: 'The user app starts or controls a workflow.',
      notes: 'User code talks to Temporal through the SDK.',
      refs: [],
    },
    {
      id: 'python-worker',
      label: 'Python Worker.run',
      layer: 'sdk-python',
      kind: 'worker',
      summary: 'The Python SDK runs worker code.',
      notes: 'The worker hosts workflow and activity execution.',
      refs: [],
    },
    {
      id: 'bridge-worker',
      label: 'Bridge worker',
      layer: 'bridge',
      kind: 'bridge',
      summary: 'The bridge connects Python to core.',
      notes: 'Bridge preserves the SDK boundary.',
      refs: [],
    },
    {
      id: 'core-runtime',
      label: 'Core runtime',
      layer: 'sdk-core',
      kind: 'runtime',
      summary: 'Core runtime hosts SDK internals.',
      notes: 'Runtime state lives below the language SDK.',
      refs: [],
    },
    {
      id: 'core-worker',
      label: 'Core worker',
      layer: 'sdk-core',
      kind: 'worker',
      summary: 'Core worker polls and completes tasks.',
      notes: 'Core worker talks to Temporal server APIs.',
      refs: [],
    },
    {
      id: 'frontend-service',
      label: 'Frontend',
      layer: 'server',
      kind: 'frontend',
      summary: 'Frontend receives public RPCs.',
      notes: 'Frontend is the server entrypoint.',
      refs: [],
    },
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
    {
      id: 'matching-service',
      label: 'Matching',
      layer: 'server',
      kind: 'matching',
      summary: 'Matching dispatches tasks to workers.',
      notes: 'Matching owns task queue delivery.',
      refs: [],
    },
    {
      id: 'activity-task',
      label: 'Activity task',
      layer: 'sdk-python',
      kind: 'activity',
      summary: 'Activity task execution happens in worker code.',
      notes: 'Activities run outside deterministic workflow code.',
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
      id: 'pause-resume-signal-recorded',
      seq: 1,
      kind: 'signal',
      from: 'workflow-activation',
      to: 'history-service',
      edge_id: 'workflow-complete',
      message: 'SignalWorkflowExecution',
      summary: 'A pause request is recorded durably.',
      details: ['History stores the signal event.'],
      affected_node_ids: ['workflow-activation', 'history-service'],
      affected_edge_ids: ['workflow-complete'],
    },
    {
      id: 'pause-resume-activation',
      seq: 2,
      kind: 'activation',
      from: 'history-service',
      to: 'workflow-activation',
      edge_id: 'workflow-complete',
      message: 'WorkflowActivation(signal)',
      summary: 'The signal is delivered to workflow code.',
      details: ['Python updates deterministic pause state.'],
      affected_node_ids: ['workflow-activation', 'history-service'],
      affected_edge_ids: ['workflow-complete'],
    },
  ],
}

const scrollIntoView = vi.fn()

describe('ControlPathsExplorer', () => {
  beforeEach(() => {
    scrollIntoView.mockClear()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    })
  })

  afterEach(() => {
    cleanup()
  })

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
    expect(screen.getByText('Print control-path overlays.')).toBeTruthy()
    const diagram = screen.getByRole('group', { name: 'Temporal lifecycle diagram' })
    expect(diagram).toBeTruthy()
    expect(diagram.textContent).toContain('User app')
    expect(diagram.textContent).toContain('Worker')
    expect(diagram.textContent).toContain('Temporal server')
    expect(diagram.textContent).toContain('Kilvin client')
    expect(diagram.textContent).toContain('Python Worker.run')
    expect(diagram.textContent).toContain('Bridge')
    expect(diagram.textContent).toContain('sdk-core')
    expect(diagram.textContent).toContain('Core worker')
    expect(diagram.textContent).toContain('Activity task')
    expect(diagram.textContent).toContain('Frontend')
    expect(diagram.textContent).toContain('History')
    expect(diagram.textContent).toContain('Matching')
    expect(screen.getByRole('button', { name: 'Activation' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Core worker' })).toBeTruthy()
  })

  it('renders an ordered control sequence and defaults to the first step details', async () => {
    render(<ControlPathsExplorer navigate={vi.fn()} />)

    const firstStep = await screen.findByRole('button', {
      name: /01 Activation to History SignalWorkflowExecution/,
    })

    expect(firstStep.getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByLabelText('Control path sequence')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'SignalWorkflowExecution' })).toBeTruthy()
    expect(screen.getAllByText('A pause request is recorded durably.').length).toBeGreaterThan(0)
    expect(screen.getByText('History stores the signal event.')).toBeTruthy()
  })

  it('updates control step details when a sequence row is selected', async () => {
    render(<ControlPathsExplorer navigate={vi.fn()} />)

    const secondStep = await screen.findByRole('button', {
      name: /02 History to Activation WorkflowActivation\(signal\)/,
    })
    fireEvent.click(secondStep)

    expect(screen.getByRole('heading', { name: 'WorkflowActivation(signal)' })).toBeTruthy()
    expect(screen.getAllByText('The signal is delivered to workflow code.').length).toBeGreaterThan(0)
    expect(screen.getByText('Python updates deterministic pause state.')).toBeTruthy()
  })

  it('selects the nearest matching control step when a diagram edge is selected', async () => {
    render(<ControlPathsExplorer navigate={vi.fn()} />)

    const secondStep = await screen.findByRole('button', {
      name: /02 History to Activation WorkflowActivation\(signal\)/,
    })
    fireEvent.click(secondStep)

    scrollIntoView.mockClear()
    const edge = screen.getByRole('button', { name: /Diagram edge WorkflowActivation\(signal\)/ })
    fireEvent.keyDown(edge, { key: 'Enter' })

    expect(screen.getByRole('heading', { name: 'WorkflowActivation(signal)' })).toBeTruthy()
    expect(secondStep.getAttribute('aria-pressed')).toBe('true')
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', behavior: 'auto' })
  })

  it('does not change selection merely because the control sequence scrolls', async () => {
    render(<ControlPathsExplorer navigate={vi.fn()} />)

    const sequence = await screen.findByLabelText('Control path sequence')
    fireEvent.scroll(sequence)

    expect(screen.getByRole('heading', { name: 'SignalWorkflowExecution' })).toBeTruthy()
  })

  it('uses the selected control step message as the diagram edge label', async () => {
    render(<ControlPathsExplorer navigate={vi.fn()} />)

    await screen.findByRole('heading', { name: 'SignalWorkflowExecution' })

    expect(screen.getByRole('button', { name: /Diagram edge SignalWorkflowExecution/ })).toBeTruthy()
    expect(screen.getAllByText('SignalWorkflowExecution').length).toBeGreaterThan(0)
  })
})
