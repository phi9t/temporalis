import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
      node_ids: ['kilvin-client', 'frontend-service'],
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
      summary: 'Starts the workflow.',
      notes: 'Client start crosses Frontend.',
      refs: [],
    },
    {
      id: 'frontend-service',
      label: 'Frontend',
      layer: 'server',
      kind: 'service',
      summary: 'Accepts workflow starts.',
      notes: 'Frontend accepts public workflow RPCs.',
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
      summary: 'Kilvin asks Temporal to start the command workflow.',
      details: ['The app submits workflow id, task queue, workflow type, and staged training input.'],
      payload: ['workflow_id', 'task_queue', 'workflow_type', 'input'],
      refs: [],
    },
    {
      id: 'call-describe-workflow',
      phase_id: 'start',
      seq: 2,
      from: 'kilvin-client',
      to: 'frontend-service',
      edge_id: 'start-rpc',
      kind: 'rpc',
      message: 'DescribeWorkflowExecution',
      summary: 'Kilvin reads the workflow execution description after start.',
      details: ['The app checks workflow execution state after submitting the start request.'],
      payload: ['run_id'],
      refs: [],
    },
    {
      id: 'call-start-workflow-response',
      phase_id: 'start',
      seq: 3,
      from: 'frontend-service',
      to: 'kilvin-client',
      edge_id: 'start-rpc',
      kind: 'response',
      message: 'StartWorkflowExecutionResponse',
      summary: 'Frontend returns the workflow start result to Kilvin.',
      details: ['The response travels back over the reused client-to-frontend edge.'],
      payload: ['run_id'],
      refs: [],
    },
    {
      id: 'call-poll-workflow-task',
      phase_id: 'poll',
      seq: 4,
      from: 'kilvin-client',
      to: 'frontend-service',
      edge_id: 'start-rpc',
      kind: 'poll',
      message: 'PollWorkflowTaskQueue',
      summary: 'The worker asks matching for workflow task work.',
      details: ['The worker long-polls for workflow task queue work after the start phase.'],
      payload: ['task_queue'],
      refs: [],
    },
  ],
}

const scrollIntoView = vi.fn()

beforeEach(() => {
  scrollIntoView.mockClear()
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: scrollIntoView,
  })
})

afterEach(() => cleanup())

describe('LifecycleExplorer', () => {
  it('renders the call sequence and defaults to the first sorted call details', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const firstCall = await screen.findByRole('button', {
      name: /01 Kilvin client to Frontend StartWorkflowExecution/,
    })

    expect(firstCall).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()
    expect(screen.getAllByText('Kilvin asks Temporal to start the command workflow.').length).toBeGreaterThan(0)
    expect(screen.getByText('workflow_id')).toBeTruthy()
  })

  it('places the call sequence before the diagram in narrow layout order', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const sequence = await screen.findByLabelText('Lifecycle call sequence')
    const diagram = screen.getByLabelText('Temporal lifecycle diagram')

    expect(sequence.compareDocumentPosition(diagram) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('updates call details when a call row is selected', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const secondCall = await screen.findByRole('button', {
      name: /02 Kilvin client to Frontend DescribeWorkflowExecution/,
    })

    fireEvent.click(secondCall)

    expect(screen.getByRole('heading', { name: 'DescribeWorkflowExecution' })).toBeTruthy()
    expect(screen.getAllByText('Kilvin reads the workflow execution description after start.').length).toBeGreaterThan(0)
    expect(screen.getByText('run_id')).toBeTruthy()
  })

  it('keeps the active phase and guide aligned when selecting a call from another phase', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const pollCall = await screen.findByRole('button', {
      name: /04 Kilvin client to Frontend PollWorkflowTaskQueue/,
    })

    fireEvent.click(pollCall)

    expect(screen.getByRole('button', { name: 'Poll workflow task' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('heading', { name: 'PollWorkflowTaskQueue' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /5\. Happy path: poll workflow task/ }).getAttribute('href')).toBe(
      '/HACKERS_GUIDE.md#happy-path-poll-workflow-task',
    )
    expect(screen.getByText('python hacks/003_lifecycle_poll.py')).toBeTruthy()
  })

  it('scrolls the selected call into view when phase or edge selection changes it', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    await screen.findByRole('button', {
      name: /01 Kilvin client to Frontend StartWorkflowExecution/,
    })

    scrollIntoView.mockClear()
    fireEvent.click(screen.getByRole('button', { name: 'Poll workflow task' }))

    expect(screen.getByRole('heading', { name: 'PollWorkflowTaskQueue' })).toBeTruthy()
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', behavior: 'auto' })

    scrollIntoView.mockClear()
    fireEvent.click(screen.getByRole('button', { name: 'Start workflow' }))
    expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()

    const edge = screen.getByRole('button', { name: /Diagram edge StartWorkflowExecution/ })
    fireEvent.keyDown(edge, { key: 'Enter' })

    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', behavior: 'auto' })
  })

  it('does not change selection merely because the call sequence scrolls', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const sequence = await screen.findByLabelText('Lifecycle call sequence')
    fireEvent.scroll(sequence)

    expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()
  })

  it('selects the first active-phase call when a diagram edge is clicked', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const responseCall = await screen.findByRole('button', {
      name: /03 Frontend to Kilvin client StartWorkflowExecutionResponse/,
    })

    fireEvent.click(responseCall)
    expect(screen.getByRole('heading', { name: 'StartWorkflowExecutionResponse' })).toBeTruthy()

    const edgeHit = document.querySelector('.lifecycle-edge .lifecycle-edge-hit')
    if (!edgeHit) throw new Error('expected lifecycle edge hit target')

    fireEvent.click(edgeHit)

    expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()
    expect(screen.getByText('workflow_id')).toBeTruthy()
  })

  it('selects a diagram edge with the keyboard', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const responseCall = await screen.findByRole('button', {
      name: /03 Frontend to Kilvin client StartWorkflowExecutionResponse/,
    })
    fireEvent.click(responseCall)
    expect(screen.getByRole('heading', { name: 'StartWorkflowExecutionResponse' })).toBeTruthy()

    const edge = screen.getByRole('button', { name: /Diagram edge StartWorkflowExecution/ })

    fireEvent.keyDown(edge, { key: 'Enter' })

    expect(screen.getByRole('heading', { name: 'StartWorkflowExecution' })).toBeTruthy()
    expect(edge.getAttribute('aria-pressed')).toBe('true')
  })

  it('renders selected response calls in call direction on reused edges', async () => {
    render(<LifecycleExplorer navigate={vi.fn()} />)

    const responseCall = await screen.findByRole('button', {
      name: /03 Frontend to Kilvin client StartWorkflowExecutionResponse/,
    })

    fireEvent.click(responseCall)

    const selectedLine = document.querySelector('.lifecycle-edge.selected .lifecycle-edge-line')

    expect(selectedLine?.getAttribute('y1')).toBe('483')
    expect(selectedLine?.getAttribute('y2')).toBe('83')
  })

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
