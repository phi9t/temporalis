import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BasicsExplorer from './BasicsExplorer'

afterEach(() => cleanup())

describe('BasicsExplorer', () => {
  it('explains Temporal through an LLM training story and the six core concepts', () => {
    render(<BasicsExplorer navigate={vi.fn()} />)

    expect(screen.getAllByText(/train model X on FineWeb with 64 A100 GPUs/).length).toBeGreaterThan(0)
    expect(screen.getByText(/materialization process durable, inspectable, retryable, resumable, and overrideable/)).toBeTruthy()

    for (const concept of ['Workflow', 'Activity', 'Worker', 'Task Queue', 'History', 'Replay']) {
      expect(screen.getByRole('heading', { name: concept })).toBeTruthy()
    }

    const timeline = screen.getByRole('list', { name: 'Model training workflow timeline' })
    const timelineText = timeline.textContent ?? ''
    const timelineLabels = [
      'Interpret training intent',
      'Build image and deps',
      'Query quota and cluster options',
      'Choose target cluster',
      'Reserve machines and locate data',
      'Materialize job spec',
      'Submit and monitor with k8s',
      'Resume or override',
    ]

    for (const label of timelineLabels) {
      expect(timelineText).toContain(label)
    }
    for (let index = 1; index < timelineLabels.length; index += 1) {
      expect(timelineText.indexOf(timelineLabels[index])).toBeGreaterThan(timelineText.indexOf(timelineLabels[index - 1]))
    }

    const artifacts = screen.getByRole('region', { name: 'Hood-open artifacts' })
    const artifactText = artifacts.textContent ?? ''
    expect(artifactText).toContain('Materialized job spec')
    expect(artifactText).toContain('env vars')
    expect(artifactText).toContain('Quota decision')
    expect(artifactText).toContain('Logs and events')
  })

  it('navigates into the existing deep-dive modes', () => {
    const navigate = vi.fn()
    render(<BasicsExplorer navigate={navigate} />)

    fireEvent.click(screen.getByRole('button', { name: 'Lifecycle Deep Dive' }))
    expect(navigate).toHaveBeenCalledWith('lifecycle')

    fireEvent.click(screen.getByRole('button', { name: 'Control Paths' }))
    expect(navigate).toHaveBeenCalledWith('control')
  })
})
