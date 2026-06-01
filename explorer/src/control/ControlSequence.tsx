import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ControlStep } from '@/lifecycle/types'

function sequenceLabel(seq: number): string {
  return String(seq).padStart(2, '0')
}

function endpointLabel(nodeLabels: Map<string, string>, nodeId: string | null): string {
  if (!nodeId) return 'Control path'

  return nodeLabels.get(nodeId) ?? nodeId
}

export default function ControlSequence({
  steps,
  nodeLabels,
  selectedStepId,
  onSelect,
  registerStepRow,
}: {
  steps: ControlStep[]
  nodeLabels: Map<string, string>
  selectedStepId: string | null
  onSelect: (step: ControlStep) => void
  registerStepRow?: (stepId: string, element: HTMLButtonElement | null) => void
}) {
  const orderedSteps = [...steps].sort((a, b) => a.seq - b.seq)

  return (
    <section className="control-sequence call-sequence" aria-label="Control path sequence">
      <div className="call-sequence-header">
        <span>Control sequence</span>
      </div>
      <div className="call-sequence-list">
        {orderedSteps.map((step) => {
          const from = endpointLabel(nodeLabels, step.from)
          const to = endpointLabel(nodeLabels, step.to)
          const seq = sequenceLabel(step.seq)
          const selected = step.id === selectedStepId

          return (
            <button
              key={step.id}
              ref={(element) => registerStepRow?.(step.id, element)}
              type="button"
              data-control-step-id={step.id}
              className={cn('call-sequence-row', selected && 'selected')}
              aria-label={`${seq} ${from} to ${to} ${step.message}`}
              aria-pressed={selected}
              onClick={() => onSelect(step)}
            >
              <span className="call-sequence-seq">{seq}</span>
              <span className="call-sequence-body">
                <span className="call-sequence-route">
                  <span>{from}</span>
                  <ArrowRight size={14} strokeWidth={2} aria-hidden="true" />
                  <span>{to}</span>
                </span>
                <span className="call-sequence-message">{step.message}</span>
                <span className="call-sequence-summary">{step.summary}</span>
              </span>
              <span className="call-sequence-kind">{step.kind}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
