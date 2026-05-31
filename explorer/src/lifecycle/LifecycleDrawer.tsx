import { BookOpen, ExternalLink, Terminal } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { guideUrl } from '@/lib/assets'
import type { LifecycleNode, LifecyclePhase } from './types'

function GuideHackPanel({ phase }: { phase: LifecyclePhase | null }) {
  if (!phase) return null

  return (
    <div className="guide-hack-panel">
      <h4 className="font-mono text-xs uppercase text-ink-muted">Read / Run / Inspect</h4>
      <a className="guide-action" href={guideUrl(phase.guide_anchor)} target="_blank" rel="noopener noreferrer">
        <BookOpen size={13} aria-hidden="true" />
        <span>{phase.guide_title}</span>
      </a>
      <div className="guide-command">
        <Terminal size={13} aria-hidden="true" />
        <code>python {phase.hack_script}</code>
      </div>
      <p className="text-xs text-ink-soft">{phase.hack_summary}</p>
    </div>
  )
}

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
          <div className="space-y-4">
            <p>{phase?.summary ?? 'Choose a lifecycle node to inspect source-backed details.'}</p>
            <p>Read the current phase, run its paired hack, then inspect a node for source refs.</p>
            <GuideHackPanel phase={phase} />
          </div>
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
        <GuideHackPanel phase={phase} />
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
