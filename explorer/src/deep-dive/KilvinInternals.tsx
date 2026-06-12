import { useEffect, useState } from 'react'
import { ArrowRight, BookOpen, ExternalLink, HeartPulse, RotateCcw, Timer } from 'lucide-react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import { cn } from '@/lib/utils'
import type { SourceRef } from '@/lifecycle/types'

interface GuideSectionLink {
  guide_anchor: string
  guide_title: string
}

interface InternalsWorkflow extends GuideSectionLink {
  name: string
  task_queue: string
  summary: string
  details: string[]
  refs: SourceRef[]
}

interface InternalsStep extends GuideSectionLink {
  id: string
  seq: number
  label: string
  activity: string
  summary: string
  details: string[]
  input_model: string
  output_model: string
  timeout_seconds: number
  retry: string
  heartbeat: boolean
  artifacts: string[]
  refs: SourceRef[]
}

interface ControlSurfaceEntry {
  name: string
  summary: string
}

interface KilvinInternalsManifest {
  generated_at: string
  workflow: InternalsWorkflow
  steps: InternalsStep[]
  signals: ControlSurfaceEntry[]
  queries: ControlSurfaceEntry[]
  control_refs: SourceRef[]
  control_guide: GuideSectionLink
  artifact_root: string
}

type InternalsSelection = { type: 'workflow' } | { type: 'step'; id: string } | { type: 'controls' }

function SourceRefLinks({ refs }: { refs: SourceRef[] }) {
  if (refs.length === 0) return null

  return (
    <div>
      <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Source refs</h4>
      <div className="space-y-2">
        {refs.map((ref) => (
          <a
            key={`${ref.path}:${ref.line}:${ref.label}`}
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

function GuideSectionAction({ link, onOpenGuide }: { link: GuideSectionLink; onOpenGuide: (anchor: string) => void }) {
  return (
    <button type="button" className="guide-action" onClick={() => onOpenGuide(link.guide_anchor)}>
      <BookOpen size={13} aria-hidden="true" />
      <span>{link.guide_title}</span>
    </button>
  )
}

function StepDetails({
  step,
  artifactRoot,
  onOpenGuide,
  onTraceLifecycle,
}: {
  step: InternalsStep
  artifactRoot: string
  onOpenGuide: (anchor: string) => void
  onTraceLifecycle: () => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.label}</CardTitle>
        <p className="font-mono text-xs text-cyan">
          {step.activity}({step.input_model}) -&gt; {step.output_model}
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="kilvin-durability" aria-label="Durability settings">
          <span>
            <Timer size={12} aria-hidden="true" /> {step.timeout_seconds}s timeout
          </span>
          <span>
            <RotateCcw size={12} aria-hidden="true" /> {step.retry}
          </span>
          {step.heartbeat ? (
            <span className="kilvin-durability--heartbeat">
              <HeartPulse size={12} aria-hidden="true" /> heartbeats
            </span>
          ) : null}
        </div>
        <p className="text-ink">{step.summary}</p>
        <ul className="call-detail-list">
          {step.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
        <div>
          <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Artifacts under {artifactRoot}</h4>
          <div className="call-detail-chips">
            {step.artifacts.map((artifact) => (
              <span key={artifact}>{artifact}</span>
            ))}
          </div>
        </div>
        <SourceRefLinks refs={step.refs} />
        <div className="kilvin-crosslinks">
          <button type="button" className="guide-action" onClick={onTraceLifecycle}>
            <ArrowRight size={13} aria-hidden="true" />
            <span>Trace how this activity executes (Lifecycle track)</span>
          </button>
          <GuideSectionAction link={step} onOpenGuide={onOpenGuide} />
        </div>
      </CardContent>
    </Card>
  )
}

function WorkflowDetails({ workflow, onOpenGuide }: { workflow: InternalsWorkflow; onOpenGuide: (anchor: string) => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{workflow.name}</CardTitle>
        <p className="font-mono text-xs text-cyan">task queue: {workflow.task_queue}</p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-ink">{workflow.summary}</p>
        <ul className="call-detail-list">
          {workflow.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
        <SourceRefLinks refs={workflow.refs} />
        <GuideSectionAction link={workflow} onOpenGuide={onOpenGuide} />
      </CardContent>
    </Card>
  )
}

function ControlSurfaceDetails({
  manifest,
  onOpenGuide,
}: {
  manifest: KilvinInternalsManifest
  onOpenGuide: (anchor: string) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Signals &amp; queries</CardTitle>
        <p className="font-mono text-xs text-cyan">durable control surface of the running workflow</p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-ink">
          Signals are durable History events that steer the run; queries read the workflow&apos;s deterministic state
          without changing it. Both work mid-flight, from the CLI or any Temporal client.
        </p>
        <div>
          <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Signals</h4>
          <dl className="kilvin-control-list">
            {manifest.signals.map((signal) => (
              <div key={signal.name}>
                <dt>{signal.name}</dt>
                <dd>{signal.summary}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div>
          <h4 className="mb-2 font-mono text-xs uppercase text-ink-muted">Queries</h4>
          <dl className="kilvin-control-list">
            {manifest.queries.map((query) => (
              <div key={query.name}>
                <dt>{query.name}</dt>
                <dd>{query.summary}</dd>
              </div>
            ))}
          </dl>
        </div>
        <SourceRefLinks refs={manifest.control_refs} />
        <GuideSectionAction link={manifest.control_guide} onOpenGuide={onOpenGuide} />
      </CardContent>
    </Card>
  )
}

/**
 * Deep Dive track for the kilvin business logic: the one training workflow,
 * what each of its six steps does, and the signal/query control surface.
 * Rendered from the generator-emitted kilvin/internals.json so the panel and
 * the Python implementation cannot drift silently.
 */
export default function KilvinInternals({
  onOpenGuide,
  onTraceLifecycle,
}: {
  onOpenGuide: (anchor: string) => void
  onTraceLifecycle: () => void
}) {
  const [manifest, setManifest] = useState<KilvinInternalsManifest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selection, setSelection] = useState<InternalsSelection>({ type: 'workflow' })

  useEffect(() => {
    fetchExplorerJson<KilvinInternalsManifest>('kilvin/internals.json')
      .then(setManifest)
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [])

  if (!manifest) {
    return (
      <AsyncBoundary
        loading={error === null}
        error={error}
        loadingLabel="Loading kilvin internals..."
        errorPrefix="Failed to load kilvin internals"
      />
    )
  }

  const selectedStep = selection.type === 'step' ? manifest.steps.find((step) => step.id === selection.id) : null

  return (
    <div className="kilvin-workspace">
      <nav className="kilvin-rail" aria-label="Kilvin internals">
        <Card className="p-4">
          <div className="kilvin-rail-heading">Intent materialization</div>
          <button
            type="button"
            className={cn('kilvin-rail-item', selection.type === 'workflow' && 'kilvin-rail-item--active')}
            aria-pressed={selection.type === 'workflow'}
            onClick={() => setSelection({ type: 'workflow' })}
          >
            <span className="kilvin-rail-seq">WF</span>
            <span>
              <span className="kilvin-rail-label">{manifest.workflow.name}</span>
              <span className="kilvin-rail-sub">{manifest.workflow.task_queue}</span>
            </span>
          </button>
          <ol className="kilvin-rail-steps">
            {manifest.steps.map((step) => (
              <li key={step.id}>
                <button
                  type="button"
                  className={cn(
                    'kilvin-rail-item',
                    selection.type === 'step' && selection.id === step.id && 'kilvin-rail-item--active',
                  )}
                  aria-pressed={selection.type === 'step' && selection.id === step.id}
                  onClick={() => setSelection({ type: 'step', id: step.id })}
                >
                  <span className="kilvin-rail-seq">{String(step.seq).padStart(2, '0')}</span>
                  <span>
                    <span className="kilvin-rail-label">{step.label}</span>
                    <span className="kilvin-rail-sub">{step.activity}</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
          <button
            type="button"
            className={cn('kilvin-rail-item', selection.type === 'controls' && 'kilvin-rail-item--active')}
            aria-pressed={selection.type === 'controls'}
            onClick={() => setSelection({ type: 'controls' })}
          >
            <span className="kilvin-rail-seq">SQ</span>
            <span>
              <span className="kilvin-rail-label">Signals &amp; queries</span>
              <span className="kilvin-rail-sub">pause · replay · inspect</span>
            </span>
          </button>
        </Card>
      </nav>

      <div className="kilvin-detail">
        {selectedStep ? (
          <StepDetails
            step={selectedStep}
            artifactRoot={manifest.artifact_root}
            onOpenGuide={onOpenGuide}
            onTraceLifecycle={onTraceLifecycle}
          />
        ) : selection.type === 'controls' ? (
          <ControlSurfaceDetails manifest={manifest} onOpenGuide={onOpenGuide} />
        ) : (
          <WorkflowDetails workflow={manifest.workflow} onOpenGuide={onOpenGuide} />
        )}
      </div>
    </div>
  )
}
