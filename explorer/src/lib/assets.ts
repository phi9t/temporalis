export const REPO_HOME = 'https://github.com/phi9t/temporalis'

export function dataUrl(path: string, base = import.meta.env.BASE_URL): string {
  const clean = path.replace(/^\//, '')
  const prefix = base === '' || base.endsWith('/') ? base : `${base}/`
  return `${prefix}${clean}`
}

export function logoMarkUrl(): string {
  return dataUrl('logo-mark.svg')
}

export function guideUrl(anchor: string, base = import.meta.env.BASE_URL): string {
  return `${dataUrl('HACKERS_GUIDE.md', base)}#${anchor}`
}

export function sourceUrl(repoUrl: string, commit: string, path: string, line?: number): string {
  const anchor = line ? `#L${line}` : ''
  return `${repoUrl.replace(/\.git$/, '')}/blob/${commit}/${path}${anchor}`
}
