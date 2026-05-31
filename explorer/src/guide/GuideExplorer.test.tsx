import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import GuideExplorer from './GuideExplorer'

vi.mock('@/lib/fetch', () => ({
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  fetchExplorerText: vi.fn(async () => `# Temporal Hacker's Guide

## 1. How to read this guide

Start here.

## 2. 30-second architecture

Read [the source](temporal/service/history/handler.go).
`),
}))

describe('GuideExplorer', () => {
  it("renders the hacker's guide with a contents rail", async () => {
    render(<GuideExplorer navigate={vi.fn()} />)

    expect(screen.getByText("Loading the Hacker's Guide...")).toBeTruthy()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: "Temporal Hacker's Guide" })).toBeTruthy()
    })

    expect(screen.getByRole('navigation', { name: 'Guide contents' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /30-second architecture/ }).getAttribute('href')).toBe(
      '#2-30-second-architecture',
    )
    expect(screen.getByRole('link', { name: 'the source' }).getAttribute('href')).toBe(
      'https://github.com/phi9t/temporalis/blob/phi9t-mainline/temporal/service/history/handler.go',
    )
  })
})
