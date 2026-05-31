import { ExternalLink } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { LifecycleNode, LifecyclePhase } from './types'

export default function LifecycleDrawer({
  node,
  phase,
}: {
  node: LifecycleNode | null
  phase: LifecyclePhase | null
}) {
  if (!node) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{phase?.label ?? 'Select a node'}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-ink-soft">
          {phase?.summary ?? 'Choose a lifecycle node to inspect source-backed details.'}
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{node.label}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {node.layer} · {node.kind}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-ink">{node.summary}</p>
        <p className="text-ink-soft">{node.notes}</p>
        <div>
          <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Source refs</h4>
          <div className="space-y-2">
            {node.refs.map((ref) => (
              <a
                key={`${ref.repo}:${ref.path}:${ref.line}`}
                className="source-link"
                href={`${ref.url}#L${ref.line}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="source-link-label">{ref.label}</span>
                <span className="source-link-path font-mono text-[11px] text-ink-muted">
                  {ref.path}:{ref.line}
                </span>
                <ExternalLink size={12} aria-hidden="true" />
              </a>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
