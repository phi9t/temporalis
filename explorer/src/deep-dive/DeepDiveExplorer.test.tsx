import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DeepDiveExplorer from './DeepDiveExplorer'
import type { ControlScenario, LifecycleManifest } from '@/lifecycle/types'

vi.mock('@/lib/fetch', () => ({
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  fetchExplorerText: vi.fn(
    async () => `# Temporal Hacker's Guide

<a id="happy-path-start-workflow-to-first-activation"></a>
## 4. Happy path: start workflow to first activation

The start request crosses into Frontend.
`,
  ),
  fetchExplorerJson: vi.fn(async (path: string) => {
    const data: Record<string, unknown> = {
      'lifecycle/index.json': [
        {
          slug: 'kilvin-asyncio-happy-path',
          label: 'Kilvin asyncio happy path',
          manifest: 'lifecycle/kilvin-asyncio-happy-path.json',
        },
      ],
      'lifecycle/kilvin-asyncio-happy-path.json': lifecycle,
      'control-paths/index.json': [
        { slug: 'pause-resume', label: 'Pause / resume', manifest: 'control-paths/pause-resume.json' },
      ],
      'control-paths/pause-resume.json': controlScenario,
      'kilvin/internals.json': kilvinInternals,
    }

    const value = data[path]
    if (!value) throw new Error(`unexpected path ${path}`)
    return value
  }),
}))

const kilvinInternals = {
  generated_at: '2026-05-31T00:00:00Z',
  workflow: {
    name: 'KilvinTrainingWorkflow',
    task_queue: 'kilvin-training-task-queue',
    summary: 'One workflow materializes one training intent end to end.',
    details: ['Every step goes through the same durable envelope.'],
    guide_anchor: 'running-example-kilvin-inspired-training-workflow',
    guide_title: '3. Running example: Kilvin-inspired training workflow',
    refs: [],
  },
  steps: [
    {
      id: 'interpret_intent',
      seq: 1,
      label: 'Interpret training intent',
      activity: 'interpret_training_intent',
      summary: 'Turns the run config into the typed plan.',
      details: ['Resolves checkpoint, config URI, and component profile.'],
      input_model: 'InterpretIntentInput',
      output_model: 'TrainingIntent',
      timeout_seconds: 30,
      retry: '3 attempts, 5s initial backoff',
      heartbeat: false,
      artifacts: ['{stage}/interpret_intent/in.yaml', '{stage}/interpret_intent/out.yaml'],
      guide_anchor: 'happy-path-start-workflow-to-first-activation',
      guide_title: '4. Happy path: start workflow to first activation',
      refs: [],
    },
    {
      id: 'monitor_training',
      seq: 2,
      label: 'Monitor training',
      activity: 'monitor_training',
      summary: 'Watches the running job and heartbeats progress.',
      details: ['Log pointers are persisted before the failure check.'],
      input_model: 'MonitorTrainingInput',
      output_model: 'MonitorOutput',
      timeout_seconds: 3600,
      retry: '3 attempts, 5s initial backoff',
      heartbeat: true,
      artifacts: ['{stage}/monitor_training/logs.yaml'],
      guide_anchor: 'happy-path-start-workflow-to-first-activation',
      guide_title: '4. Happy path: start workflow to first activation',
      refs: [],
    },
  ],
  signals: [{ name: 'pause', summary: 'Park the run before the next step.' }],
  queries: [{ name: 'run_status', summary: 'The full run state.' }],
  control_refs: [],
  control_guide: {
    guide_anchor: 'happy-path-start-workflow-to-first-activation',
    guide_title: '4. Happy path: start workflow to first activation',
  },
  artifact_root: '.kilvin-artifacts/{run_id}/{attempt}/artifacts/{stage}/{step}/',
}

const lifecycle: LifecycleManifest = {
  generated_at: '2026-05-31T00:00:00Z',
  slug: 'kilvin-asyncio-happy-path',
  label: 'Kilvin asyncio happy path',
  phases: [
    {
      id: 'start',
      label: 'Start workflow',
      summary: 'Kilvin submits a staged training run.',
      node_ids: ['kilvin-client', 'frontend-service'],
      guide_anchor: 'happy-path-start-workflow-to-first-activation',
      guide_title: '4. Happy path: start workflow to first activation',
      hack_script: 'hacks/002_lifecycle_manifest.py',
      hack_summary: 'Walk the Kilvin asyncio happy-path lifecycle manifest in phase order.',
    },
    {
      id: 'poll',
      label: 'Poll workflow task',
      summary: 'The worker polls for workflow work.',
      node_ids: ['python-worker', 'matching-service'],
      guide_anchor: 'happy-path-poll-workflow-task',
      guide_title: '5. Happy path: poll workflow task',
      hack_script: 'hacks/003_lifecycle_poll.py',
      hack_summary: 'Inspect the worker poll phase of the lifecycle manifest.',
    },
  ],
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
      id: 'workflow-activation',
      label: 'Activation',
      layer: 'sdk-python',
      kind: 'workflow',
      summary: 'Python resumes workflow code.',
      notes: 'Replay feeds deterministic activations back to Python.',
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
  ],
  edges: [
    {
      id: 'start-rpc',
      from: 'kilvin-client',
      to: 'frontend-service',
      kind: 'rpc',
      label: 'StartWorkflowExecution',
    },
    {
      id: 'workflow-complete',
      from: 'workflow-activation',
      to: 'history-service',
      kind: 'completion',
      label: 'RespondWorkflowTaskCompleted',
    },
    {
      id: 'poll-workflow-task',
      from: 'python-worker',
      to: 'matching-service',
      kind: 'poll',
      label: 'PollWorkflowTaskQueue',
    },
  ],
  calls: [
    {
      id: 'call-start-workflow',
      phase_id: 'start',
      seq: 1,
      from: 'kilvin-client',
      to: 'frontend-service',
      edge_id: 'start-rpc',
      kind: 'rpc',
      message: 'StartWorkflowExecution',
      summary: 'Kilvin asks Temporal to start the training workflow.',
      details: ['The app submits workflow id, task queue, workflow type, and staged training input.'],
      payload: ['workflow_id'],
      refs: [],
    },
    {
      id: 'call-poll-workflow-task',
      phase_id: 'poll',
      seq: 2,
      from: 'python-worker',
      to: 'matching-service',
      edge_id: 'poll-workflow-task',
      kind: 'poll',
      message: 'PollWorkflowTaskQueue',
      summary: 'The worker asks matching for workflow task work.',
      details: ['The worker long-polls for workflow task queue work after the start phase.'],
      payload: ['task_queue'],
      refs: [],
    },
  ],
}

const controlScenario: ControlScenario = {
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
    {
      id: 'pause-resume-command',
      seq: 3,
      kind: 'command',
      from: 'workflow-activation',
      to: 'history-service',
      edge_id: 'workflow-complete',
      message: 'RespondWorkflowTaskCompleted',
      summary: 'Python emits commands after resume.',
      details: ['History receives workflow task completion.'],
      affected_node_ids: ['workflow-activation', 'history-service'],
      affected_edge_ids: ['workflow-complete'],
    },
  ],
}

afterEach(() => cleanup())

describe('DeepDiveExplorer', () => {
  it('renders lifecycle as the default swimlane track', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} />)

    const diagram = await screen.findByRole('group', { name: 'Temporal swimlane flow diagram' })

    expect(screen.getByRole('button', { name: 'Lifecycle' }).getAttribute('aria-pressed')).toBe('true')
    expect(diagram.textContent).toContain('User app')
    expect(diagram.textContent).toContain('Worker')
    expect(diagram.textContent).toContain('Temporal server')
    expect(diagram.textContent).toContain('Kilvin client')
    expect(diagram.textContent).toContain('Python Worker.run')
    expect(diagram.textContent).toContain('Bridge worker')
    expect(diagram.textContent).toContain('Core worker')
    expect(diagram.textContent).toContain('Frontend')
    expect(diagram.textContent).toContain('History')
    expect(diagram.textContent).toContain('Matching')
    expect(screen.getByRole('button', { name: /Flow step 01 Kilvin client to Frontend StartWorkflowExecution/ }))
      .toBeTruthy()
  })

  it('switches to control paths in the same swimlane presentation', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} />)

    await screen.findByRole('button', { name: /Flow step 01 Kilvin client to Frontend StartWorkflowExecution/ })
    fireEvent.click(screen.getByRole('button', { name: 'Control Paths' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Control Paths' }).getAttribute('aria-pressed')).toBe('true')
    })

    const diagram = screen.getByRole('group', { name: 'Temporal swimlane flow diagram' })
    expect(screen.getByText('Signals change workflow state; replay preserves deterministic history.')).toBeTruthy()
    expect(diagram.textContent).toContain('SignalWorkflowExecution')
    expect(diagram.textContent).toContain('WorkflowActivation(signal)')
    expect(diagram.textContent).toContain('RespondWorkflowTaskCompleted')
    expect(screen.getByRole('button', { name: /Flow step 02 History to Activation WorkflowActivation\(signal\)/ }))
      .toBeTruthy()
  })

  it('keeps control paths focused on the swimlane without a detail drawer', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} />)

    await screen.findByRole('button', { name: /Flow step 01 Kilvin client to Frontend StartWorkflowExecution/ })
    fireEvent.click(screen.getByRole('button', { name: 'Control Paths' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Control Paths' }).getAttribute('aria-pressed')).toBe('true')
    })

    expect(screen.getByRole('group', { name: 'Temporal swimlane flow diagram' })).toBeTruthy()
    expect(screen.getByText(/overlay on the happy-path swimlane/)).toBeTruthy()
    expect(screen.queryByText('Read / Run / Inspect')).toBeNull()
    expect(screen.queryByText('python hacks/005_control_paths.py')).toBeNull()
  })

  it('keeps component selection inside the merged swimlane', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} />)

    const coreWorker = await screen.findByRole('button', { name: 'Core worker' })
    fireEvent.click(coreWorker)

    expect(coreWorker.getAttribute('aria-pressed')).toBe('true')
  })

  it('shows the selected call in the detail drawer and opens the guide track in place', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} />)

    await screen.findByRole('button', { name: /Flow step 01 Kilvin client to Frontend StartWorkflowExecution/ })

    expect(screen.getByText('Read / Run / Inspect')).toBeTruthy()
    expect(screen.getAllByText('Kilvin asks Temporal to start the training workflow.').length).toBeGreaterThan(1)
    expect(screen.getByText('python hacks/002_lifecycle_manifest.py')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '4. Happy path: start workflow to first activation' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: "Hacker's Guide" }).getAttribute('aria-pressed')).toBe('true')
    })
    await screen.findByRole('heading', { name: "Temporal Hacker's Guide" })
  })

  it('renders the kilvin internals track from the generated manifest', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} context={{ deepDiveTrack: 'kilvin' }} />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Kilvin Internals' }).getAttribute('aria-pressed')).toBe('true')
    })

    expect(await screen.findByRole('navigation', { name: 'Kilvin internals' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'KilvinTrainingWorkflow' })).toBeTruthy()
    expect(screen.getByText('task queue: kilvin-training-task-queue')).toBeTruthy()
    expect(screen.getByText('Every step goes through the same durable envelope.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /02.*Monitor training/ }))

    expect(screen.getByRole('heading', { name: 'Monitor training' })).toBeTruthy()
    expect(screen.getByText('3600s timeout')).toBeTruthy()
    expect(screen.getByText('heartbeats')).toBeTruthy()
    expect(screen.getByText('{stage}/monitor_training/logs.yaml')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /SQ.*Signals & queries/ }))
    expect(screen.getByText('Park the run before the next step.')).toBeTruthy()
    expect(screen.getByText('run_status')).toBeTruthy()
  })

  it('traces a kilvin step into the lifecycle track', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} context={{ deepDiveTrack: 'kilvin' }} />)

    await screen.findByRole('navigation', { name: 'Kilvin internals' })
    fireEvent.click(screen.getByRole('button', { name: /01.*Interpret training intent/ }))
    fireEvent.click(screen.getByRole('button', { name: /Trace how this activity executes/ }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Lifecycle' }).getAttribute('aria-pressed')).toBe('true')
    })
    expect(screen.getByRole('group', { name: 'Temporal swimlane flow diagram' })).toBeTruthy()
  })

  it('renders a swimlane legend on both tracks', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} />)

    await screen.findByRole('note', { name: 'Swimlane legend' })
    expect(screen.getByRole('note', { name: 'Swimlane legend' }).textContent).toContain('User app lane')

    fireEvent.click(screen.getByRole('button', { name: 'Control Paths' }))

    await waitFor(() => {
      expect(screen.getByRole('note', { name: 'Swimlane legend' }).textContent).toContain(
        'Overlay = diverges from the happy path',
      )
    })
  })

  it('frames control paths as overlays and marks diverging steps', async () => {
    render(<DeepDiveExplorer navigate={vi.fn()} />)

    await screen.findByRole('button', { name: /Flow step 01 Kilvin client to Frontend StartWorkflowExecution/ })
    fireEvent.click(screen.getByRole('button', { name: 'Control Paths' }))

    await waitFor(() => {
      expect(screen.getByText(/overlay on the happy-path swimlane/)).toBeTruthy()
    })

    const signalStep = screen.getByRole('button', {
      name: /Flow step 01 Activation to History SignalWorkflowExecution/,
    })
    expect(signalStep.className).toContain('flow-step-card--overlay')
    expect(screen.getAllByText('A pause request is recorded durably.').length).toBeGreaterThan(0)
    expect(screen.queryByText('python hacks/005_control_paths.py')).toBeNull()
  })

  it('opens directly on a control scenario from a navigation context', async () => {
    render(
      <DeepDiveExplorer
        navigate={vi.fn()}
        context={{ deepDiveTrack: 'control', deepDiveScenarioSlug: 'pause-resume' }}
      />,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Control Paths' }).getAttribute('aria-pressed')).toBe('true')
    })
    await screen.findByText('Signals change workflow state; replay preserves deterministic history.')
  })

  it('opens directly on a lifecycle phase from a navigation context', async () => {
    render(
      <DeepDiveExplorer navigate={vi.fn()} context={{ deepDiveTrack: 'lifecycle', deepDivePhaseId: 'poll' }} />,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Poll workflow task' }).getAttribute('aria-pressed')).toBe('true')
    })
    expect(screen.getAllByText('The worker asks matching for workflow task work.').length).toBeGreaterThan(1)
  })
})
