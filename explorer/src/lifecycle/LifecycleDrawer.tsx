import { BookOpen, ExternalLink, Terminal } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { guideUrl } from '@/lib/assets'
import type {
  ControlSelection,
  ControlStep,
  GuideHackLink,
  LifecycleCall,
  LifecycleNode,
  LifecyclePhase,
  LifecycleSelection,
  SourceRef,
} from './types'

function GuideHackPanel({
  link,
  onOpenGuide,
}: {
  link: GuideHackLink | null
  onOpenGuide?: (anchor: string) => void
}) {
  if (!link) return null

  return (
    <div className="guide-hack-panel">
      <h4 className="font-mono text-xs uppercase text-ink-muted">Read / Run / Inspect</h4>
      {onOpenGuide ? (
        <button type="button" className="guide-action" onClick={() => onOpenGuide(link.guide_anchor)}>
          <BookOpen size={13} aria-hidden="true" />
          <span>{link.guide_title}</span>
        </button>
      ) : (
        <a className="guide-action" href={guideUrl(link.guide_anchor)} target="_blank" rel="noopener noreferrer">
          <BookOpen size={13} aria-hidden="true" />
          <span>{link.guide_title}</span>
        </a>
      )}
      <div className="guide-command">
        <Terminal size={13} aria-hidden="true" />
        <code>python {link.hack_script}</code>
      </div>
      <p className="text-xs text-ink-soft">{link.hack_summary}</p>
    </div>
  )
}

function SourceRefs({ refs }: { refs: SourceRef[] }) {
  if (refs.length === 0) return null

  return (
    <div>
      <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Source refs</h4>
      <div className="space-y-2">
        {refs.map((ref) => (
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
  )
}

function CallDetails({
  call,
  phase,
  nodeLabels,
  phaseLabels,
  onOpenGuide,
}: {
  call: LifecycleCall
  phase: LifecyclePhase | null
  nodeLabels: Map<string, string>
  phaseLabels: Map<string, string>
  onOpenGuide?: (anchor: string) => void
}) {
  const from = nodeLabels.get(call.from) ?? call.from
  const to = nodeLabels.get(call.to) ?? call.to
  const phaseLabel = phaseLabels.get(call.phase_id) ?? call.phase_id

  return (
    <Card>
      <CardHeader>
        <CardTitle>{call.message}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {from} -&gt; {to}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="call-detail-meta">
          <span>{call.kind}</span>
          <span>{phaseLabel}</span>
        </div>
        <p className="text-ink">{call.summary}</p>
        <ul className="call-detail-list">
          {call.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
        {call.payload && call.payload.length > 0 && (
          <div>
            <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Payload</h4>
            <div className="call-detail-chips">
              {call.payload.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </div>
        )}
        <SourceRefs refs={call.refs} />
        <GuideHackPanel link={phase} onOpenGuide={onOpenGuide} />
      </CardContent>
    </Card>
  )
}

function ControlStepDetails({
  step,
  guide,
  nodeLabels,
  onOpenGuide,
}: {
  step: ControlStep
  guide: GuideHackLink | null
  nodeLabels: Map<string, string>
  onOpenGuide?: (anchor: string) => void
}) {
  const from = step.from ? (nodeLabels.get(step.from) ?? step.from) : 'Control path'
  const to = step.to ? (nodeLabels.get(step.to) ?? step.to) : 'Control path'

  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.message}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {from} -&gt; {to}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="call-detail-meta">
          <span>{step.kind}</span>
          <span>Control path</span>
        </div>
        <p className="text-ink">{step.summary}</p>
        <ul className="call-detail-list">
          {step.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
        <GuideHackPanel link={guide} onOpenGuide={onOpenGuide} />
      </CardContent>
    </Card>
  )
}

export default function LifecycleDrawer({
  selection,
  node,
  phase,
  guide = null,
  nodeLabels = new Map<string, string>(),
  phaseLabels = new Map<string, string>(),
  onOpenGuide,
}: {
  selection?: LifecycleSelection | ControlSelection | null
  node?: LifecycleNode | null
  phase: LifecyclePhase | null
  guide?: GuideHackLink | null
  nodeLabels?: Map<string, string>
  phaseLabels?: Map<string, string>
  onOpenGuide?: (anchor: string) => void
}) {
  const selected = selection ?? (node ? { type: 'node' as const, node } : null)
  const guideLink = phase ?? guide

  if (!selected) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{phase?.label ?? 'Select a node'}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-ink-soft">
          <div className="space-y-4">
            <p>{phase?.summary ?? 'Choose a lifecycle node to inspect source-backed details.'}</p>
            <p>Read the current phase, run its paired hack, then inspect a node for source refs.</p>
            <GuideHackPanel link={guideLink} onOpenGuide={onOpenGuide} />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (selected.type === 'control-step') {
    return <ControlStepDetails step={selected.step} guide={guide} nodeLabels={nodeLabels} onOpenGuide={onOpenGuide} />
  }

  if (selected.type === 'call') {
    return (
      <CallDetails
        call={selected.call}
        phase={phase}
        nodeLabels={nodeLabels}
        phaseLabels={phaseLabels}
        onOpenGuide={onOpenGuide}
      />
    )
  }

  const selectedNode = selected.node

  return (
    <Card>
      <CardHeader>
        <CardTitle>{selectedNode.label}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {selectedNode.layer} · {selectedNode.kind}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-ink">{selectedNode.summary}</p>
        <p className="text-ink-soft">{selectedNode.notes}</p>
        <GuideHackPanel link={guideLink} onOpenGuide={onOpenGuide} />
        <SourceRefs refs={selectedNode.refs} />
      </CardContent>
    </Card>
  )
}
