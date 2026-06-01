import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CallSequence from './CallSequence'
import type { LifecycleCall } from './types'

const calls: LifecycleCall[] = [
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
    refs: [],
  },
  {
    id: 'call-poll-workflow-task',
    phase_id: 'activation',
    seq: 2,
    from: 'python-worker',
    to: 'matching-service',
    edge_id: 'poll-rpc',
    kind: 'poll',
    message: 'PollWorkflowTaskQueue',
    summary: 'The worker asks matching for workflow work.',
    details: ['The worker holds a long poll for the configured task queue.'],
    refs: [],
  },
]

const nodeLabels = new Map([
  ['kilvin-client', 'Kilvin client'],
  ['frontend-service', 'Frontend'],
  ['python-worker', 'Python worker'],
  ['matching-service', 'Matching'],
])

afterEach(() => cleanup())

describe('CallSequence', () => {
  it('renders ordered call rows with endpoint labels and messages', () => {
    render(
      <CallSequence
        calls={[calls[1], calls[0]]}
        nodeLabels={nodeLabels}
        activePhaseId="start"
        selectedCallId={null}
        onSelect={vi.fn()}
      />,
    )

    const rows = screen.getAllByRole('button')

    expect(rows).toHaveLength(2)
    expect(rows[0].getAttribute('aria-label')).toContain('01 Kilvin client to Frontend StartWorkflowExecution')
    expect(rows[1].getAttribute('aria-label')).toContain('02 Python worker to Matching PollWorkflowTaskQueue')
    expect(screen.getByText('Kilvin client')).toBeTruthy()
    expect(screen.getByText('Frontend')).toBeTruthy()
    expect(screen.getByText('StartWorkflowExecution')).toBeTruthy()
  })

  it('represents active phase and selected row states', () => {
    render(
      <CallSequence
        calls={calls}
        nodeLabels={nodeLabels}
        activePhaseId="activation"
        selectedCallId="call-poll-workflow-task"
        onSelect={vi.fn()}
      />,
    )

    const selected = screen.getByRole('button', {
      name: /02 Python worker to Matching PollWorkflowTaskQueue/,
    })

    expect(selected.getAttribute('data-active-phase')).toBe('true')
    expect(selected.getAttribute('aria-pressed')).toBe('true')
  })

  it('calls onSelect with the selected lifecycle call when a row is clicked', () => {
    const onSelect = vi.fn()

    render(
      <CallSequence
        calls={calls}
        nodeLabels={nodeLabels}
        activePhaseId="start"
        selectedCallId={null}
        onSelect={onSelect}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /02 Python worker to Matching PollWorkflowTaskQueue/ }))

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith(calls[1])
  })
})
