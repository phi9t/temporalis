export const REPO_HOME = 'https://github.com/phi9t/temporalis'

export function dataUrl(path: string, base = import.meta.env.BASE_URL): string {
  const clean = path.replace(/^\//, '')
  const prefix = base === '' || base.endsWith('/') ? base : `${base}/`
  return `${prefix}${clean}`
}

export function guideUrl(anchor: string, base = import.meta.env.BASE_URL): string {
  return `${dataUrl('HACKERS_GUIDE.md', base)}#${anchor}`
}

export function repoFileUrl(path: string, ref = 'phi9t-mainline'): string {
  return `${REPO_HOME}/blob/${ref}/${path.replace(/^\//, '')}`
}

export function sourceUrl(repoUrl: string, commit: string, path: string, line?: number): string {
  const anchor = line ? `#L${line}` : ''
  return `${repoUrl.replace(/\.git$/, '')}/blob/${commit}/${path}${anchor}`
}
