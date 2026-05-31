import { describe, expect, it } from 'vitest'
import { dataUrl, guideUrl } from './assets'

describe('asset URLs', () => {
  it('joins public asset paths with base paths that omit trailing slashes', () => {
    const dataUrlWithBase = dataUrl as (path: string, base: string) => string
    const guideUrlWithBase = guideUrl as (anchor: string, base: string) => string

    expect(dataUrlWithBase('data/lifecycle/index.json', '/temporalis-explorer')).toBe(
      '/temporalis-explorer/data/lifecycle/index.json',
    )
    expect(guideUrlWithBase('happy-path-start-workflow-to-first-activation', '/temporalis-explorer')).toBe(
      '/temporalis-explorer/HACKERS_GUIDE.md#happy-path-start-workflow-to-first-activation',
    )
  })

  it('preserves existing root and trailing-slash base behavior', () => {
    const dataUrlWithBase = dataUrl as (path: string, base: string) => string
    const guideUrlWithBase = guideUrl as (anchor: string, base: string) => string

    expect(dataUrlWithBase('/logo-mark.svg', '/')).toBe('/logo-mark.svg')
    expect(dataUrlWithBase('logo-mark.svg', '/temporalis-explorer/')).toBe(
      '/temporalis-explorer/logo-mark.svg',
    )
    expect(guideUrlWithBase('retry-and-failure-handling', '/temporalis-explorer/')).toBe(
      '/temporalis-explorer/HACKERS_GUIDE.md#retry-and-failure-handling',
    )
  })
})
