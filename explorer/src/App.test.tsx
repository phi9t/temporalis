import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
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

  it('walks the learning path with next and previous controls', () => {
    render(<App />)

    const footer = screen.getByRole('contentinfo', { name: 'Learning path' })

    expect(footer.textContent).toContain('Start here: one training run told in plain language.')
    expect(footer.textContent).toContain('Deep Dive')
    expect(footer.textContent).not.toContain('Basics')

    fireEvent.click(within(footer).getByRole('button', { name: /Deep Dive/ }))

    expect(screen.getByRole('button', { name: 'Deep Dive' }).getAttribute('aria-pressed')).toBe('true')
    const updatedFooter = screen.getByRole('contentinfo', { name: 'Learning path' })
    expect(updatedFooter.textContent).toContain('Basics')
    expect(updatedFooter.textContent).toContain("Hacker's Guide")
  })
})
