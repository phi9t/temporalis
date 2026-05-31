export const REPO_HOME = 'https://github.com/phi9t/temporalis'

export function dataUrl(path: string): string {
  const clean = path.replace(/^\//, '')
  return `${import.meta.env.BASE_URL}${clean}`
}

export function logoMarkUrl(): string {
  return dataUrl('logo-mark.svg')
}

export function guideUrl(anchor: string): string {
  return `${import.meta.env.BASE_URL}HACKERS_GUIDE.md#${anchor}`
}

export function sourceUrl(repoUrl: string, commit: string, path: string, line?: number): string {
  const anchor = line ? `#L${line}` : ''
  return `${repoUrl.replace(/\.git$/, '')}/blob/${commit}/${path}${anchor}`
}
