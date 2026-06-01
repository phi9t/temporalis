import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LifecycleCall } from './types'

function sequenceLabel(seq: number): string {
  return String(seq).padStart(2, '0')
}

function endpointLabel(nodeLabels: Map<string, string>, nodeId: string): string {
  return nodeLabels.get(nodeId) ?? nodeId
}

export default function CallSequence({
  calls,
  nodeLabels,
  activePhaseId,
  selectedCallId,
  onSelect,
}: {
  calls: LifecycleCall[]
  nodeLabels: Map<string, string>
  activePhaseId: string
  selectedCallId: string | null
  onSelect: (call: LifecycleCall) => void
}) {
  const orderedCalls = [...calls].sort((a, b) => a.seq - b.seq)

  return (
    <section className="call-sequence" aria-label="Lifecycle call sequence">
      <div className="call-sequence-header">
        <span>Call sequence</span>
      </div>
      <div className="call-sequence-list">
        {orderedCalls.map((call) => {
          const from = endpointLabel(nodeLabels, call.from)
          const to = endpointLabel(nodeLabels, call.to)
          const seq = sequenceLabel(call.seq)
          const active = call.phase_id === activePhaseId
          const selected = call.id === selectedCallId

          return (
            <button
              key={call.id}
              type="button"
              className={cn('call-sequence-row', active && 'active', selected && 'selected')}
              aria-label={`${seq} ${from} to ${to} ${call.message}${active ? ' Current phase call' : ''}`}
              aria-pressed={selected}
              data-active-phase={active}
              onClick={() => onSelect(call)}
            >
              {active && <span className="visually-hidden">Current phase call</span>}
              <span className="call-sequence-seq">{seq}</span>
              <span className="call-sequence-body">
                <span className="call-sequence-route">
                  <span>{from}</span>
                  <ArrowRight size={14} strokeWidth={2} aria-hidden="true" />
                  <span>{to}</span>
                </span>
                <span className="call-sequence-message">{call.message}</span>
                <span className="call-sequence-summary">{call.summary}</span>
              </span>
              <span className="call-sequence-kind">{call.kind}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
