import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'

afterEach(() => cleanup())

describe('App', () => {
  it('opens on Basics and keeps the merged explorer modes available', () => {
    render(<App />)

    const nav = screen.getByRole('navigation', { name: 'Explorer section' })

    expect(screen.getByRole('button', { name: 'Basics' }).getAttribute('aria-pressed')).toBe('true')
    expect(nav.querySelectorAll('button')).toHaveLength(3)
    expect(nav.textContent).toContain('Deep Dive')
    expect(nav.textContent).not.toContain('Lifecycle Deep Dive')
    expect(nav.textContent).not.toContain('Control Paths')
    expect(nav.textContent).toContain("Hacker's Guide")
    expect(screen.getByText(/Workflows, activities, task queues, history, workers, retry, and replay/)).toBeTruthy()
  })
})
