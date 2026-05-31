import { useEffect, useId, useMemo, useRef, useState } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { Card } from '@/components/ui/card'
import { REPO_HOME } from '@/lib/assets'
import { errorMessage, fetchExplorerText } from '@/lib/fetch'
import type { ExplorerModeProps } from '@/explorer-kit/mode'

const REF = 'phi9t-mainline'

function rewriteHref(href?: string): { href: string; external: boolean } {
  if (!href) return { href: '#', external: false }
  if (href.startsWith('#')) return { href, external: false }
  if (/^https?:\/\//.test(href) || href.startsWith('mailto:')) {
    return { href, external: true }
  }
  const clean = href.replace(/^\.?\//, '')
  const kind = clean.endsWith('/') ? 'tree' : 'blob'
  return { href: `${REPO_HOME}/${kind}/${REF}/${clean}`, external: true }
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9 -]/g, '')
    .replace(/ /g, '-')
}

let mermaidReady: Promise<typeof import('mermaid').default> | null = null

function loadMermaid() {
  if (!mermaidReady) {
    mermaidReady = import('mermaid').then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'base',
        themeVariables: {
          darkMode: true,
          fontFamily: 'Fira Code Variable, ui-monospace, monospace',
          fontSize: '13px',
          background: '#0b0f19',
          primaryColor: '#161d2e',
          primaryBorderColor: '#6366f1',
          primaryTextColor: '#f3f4f6',
          secondaryColor: '#16233a',
          tertiaryColor: '#1d1838',
          lineColor: '#38bdf8',
          textColor: '#cbd5e1',
          titleColor: '#f3f4f6',
          clusterBkg: 'rgba(99,102,241,0.06)',
          clusterBorder: 'rgba(99,102,241,0.35)',
          edgeLabelBackground: '#0b0f19',
        },
      })
      return mermaid
    })
  }
  return mermaidReady
}

function Mermaid({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const rawId = useId()
  const id = `mmd-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`

  useEffect(() => {
    let cancelled = false
    loadMermaid()
      .then((mermaid) => mermaid.render(id, chart))
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [chart, id])

  if (failed) return <pre className="guide-mermaid-src">{chart}</pre>
  return <div className="guide-mermaid" role="img" aria-label="diagram" ref={ref} />
}

function isMermaidNode(node: unknown): boolean {
  const child = (node as { children?: { properties?: { className?: unknown } }[] })?.children?.[0]
  const cls = child?.properties?.className
  return Array.isArray(cls) && cls.some((c) => String(c).includes('language-mermaid'))
}

const components: Components = {
  a({ href, children, node: _node, ...rest }) {
    const rewritten = rewriteHref(href)
    const external = rewritten.external ? { target: '_blank', rel: 'noopener noreferrer' } : {}
    return (
      <a href={rewritten.href} {...external} {...rest}>
        {children}
      </a>
    )
  },
  code({ className, children, node: _node, ...rest }) {
    if (/\blanguage-mermaid\b/.test(className || '')) {
      return <Mermaid chart={String(children).trim()} />
    }
    return (
      <code className={className} {...rest}>
        {children}
      </code>
    )
  },
  pre({ node, children, ...rest }) {
    if (isMermaidNode(node)) return <>{children}</>
    return <pre {...rest}>{children}</pre>
  },
}

export default function GuideExplorer(_props: ExplorerModeProps) {
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchExplorerText('guide.md')
      .then(setMarkdown)
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [])

  const toc = useMemo(() => {
    if (!markdown) return []
    const sections: { num: string; title: string; id: string }[] = []
    for (const line of markdown.split('\n')) {
      const match = /^## (\d+)\. (.+)$/.exec(line)
      if (!match) continue
      const title = match[2].replace(/`/g, '')
      sections.push({
        num: match[1],
        title,
        id: slugify(`${match[1]}. ${title}`),
      })
    }
    return sections
  }, [markdown])
  const renderedMarkdown = useMemo(
    () => markdown?.replace(/^<a\s+id="[^"]+"><\/a>\n/gm, '') ?? '',
    [markdown],
  )

  if (!markdown) {
    return (
      <AsyncBoundary
        loading={error === null}
        error={error}
        loadingLabel="Loading the Hacker's Guide..."
        errorPrefix="Failed to load guide.md"
      />
    )
  }

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[248px_1fr]">
      <nav aria-label="Guide contents" className="hidden lg:block lg:sticky lg:top-6">
        <Card className="p-4">
          <div className="mb-2 text-[11px] uppercase text-ink-muted">Contents</div>
          <ol className="flex flex-col gap-1">
            {toc.map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="block truncate text-xs text-ink-soft transition-colors hover:text-cyan"
                  title={section.title}
                >
                  <span className="text-ink-muted">{section.num}.</span> {section.title}
                </a>
              </li>
            ))}
          </ol>
        </Card>
      </nav>

      <Card className="guide p-6 md:p-8">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]} components={components}>
          {renderedMarkdown}
        </ReactMarkdown>
      </Card>
    </div>
  )
}
