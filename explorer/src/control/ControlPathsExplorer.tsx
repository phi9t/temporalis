import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BookOpen, Terminal } from 'lucide-react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { guideUrl } from '@/lib/assets'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import LifecycleDiagram from '@/lifecycle/LifecycleDiagram'
import LifecycleDrawer from '@/lifecycle/LifecycleDrawer'
import ControlSequence from './ControlSequence'
import type { EdgeLabelCall } from '@/lifecycle/LifecycleDiagram'
import type { ControlScenario, ControlSelection, ControlStep, LifecycleManifest } from '@/lifecycle/types'

interface ControlEntry {
  slug: string
  label: string
  manifest: string
}

function stepToEdgeLabelCall(step: ControlStep): EdgeLabelCall | null {
  if (!step.from || !step.to || !step.edge_id) return null

  return {
    id: step.id,
    phase_id: 'control-path',
    seq: step.seq,
    edge_id: step.edge_id,
    message: step.message,
  }
}

export default function ControlPathsExplorer(_props: ExplorerModeProps) {
  const [lifecycle, setLifecycle] = useState<LifecycleManifest | null>(null)
  const [index, setIndex] = useState<ControlEntry[] | null>(null)
  const [slug, setSlug] = useState<string>('')
  const [scenario, setScenario] = useState<ControlScenario | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ControlSelection | null>(null)
  const [revealRequestId, setRevealRequestId] = useState(0)
  const stepRowsRef = useRef(new Map<string, HTMLButtonElement>())
  const shouldScrollSelectedStepRef = useRef(false)

  useEffect(() => {
    let isCurrent = true

    Promise.all([
      fetchExplorerJson<LifecycleManifest>('lifecycle/kilvin-asyncio-happy-path.json'),
      fetchExplorerJson<ControlEntry[]>('control-paths/index.json'),
    ])
      .then(([loadedLifecycle, loadedIndex]) => {
        if (!isCurrent) return

        setLifecycle(loadedLifecycle)
        setIndex(loadedIndex)
        setSlug(loadedIndex[0]?.slug ?? '')
      })
      .catch((err: unknown) => {
        if (!isCurrent) return

        setError(errorMessage(err))
      })

    return () => {
      isCurrent = false
    }
  }, [])

  const entry = index?.find((item) => item.slug === slug) ?? null
  const controlSteps = useMemo(
    () => (scenario ? [...scenario.steps].sort((a, b) => a.seq - b.seq) : []),
    [scenario],
  )
  const selectedStep = selected?.type === 'control-step' ? selected.step : null
  const selectedNode = selected?.type === 'node' ? selected.node : null
  const selectedCall = selectedStep ? stepToEdgeLabelCall(selectedStep) : null

  const registerStepRow = useCallback((stepId: string, element: HTMLButtonElement | null) => {
    if (element) {
      stepRowsRef.current.set(stepId, element)
      return
    }

    stepRowsRef.current.delete(stepId)
  }, [])

  const selectStep = useCallback((step: ControlStep) => {
    setSelected({ type: 'control-step', step })
  }, [])

  const selectStepAndReveal = useCallback(
    (step: ControlStep) => {
      shouldScrollSelectedStepRef.current = true
      setRevealRequestId((requestId) => requestId + 1)
      selectStep(step)
    },
    [selectStep],
  )

  useEffect(() => {
    if (!entry) return

    let isCurrent = true

    fetchExplorerJson<ControlScenario>(entry.manifest)
      .then((loaded) => {
        if (!isCurrent) return

        const sortedSteps = [...loaded.steps].sort((a, b) => a.seq - b.seq)

        setScenario(loaded)
        setSelected(sortedSteps[0] ? { type: 'control-step', step: sortedSteps[0] } : null)
      })
      .catch((err: unknown) => {
        if (!isCurrent) return

        setError(errorMessage(err))
      })

    return () => {
      isCurrent = false
    }
  }, [entry])

  function handleSlugChange(nextSlug: string) {
    setSlug(nextSlug)
    setScenario(null)
    setError(null)
    setSelected(null)
  }

  useEffect(() => {
    stepRowsRef.current.clear()
  }, [slug])

  useEffect(() => {
    if (!selectedStep || !shouldScrollSelectedStepRef.current) return

    shouldScrollSelectedStepRef.current = false
    stepRowsRef.current.get(selectedStep.id)?.scrollIntoView({ block: 'nearest', behavior: 'auto' })
  }, [revealRequestId, selectedStep])

  const activeNodeIds = useMemo(
    () => new Set([...(scenario?.highlight_node_ids ?? []), ...(selectedStep?.affected_node_ids ?? [])]),
    [scenario, selectedStep],
  )
  const activeEdgeIds = useMemo(
    () => new Set([...(scenario?.highlight_edge_ids ?? []), ...(selectedStep?.affected_edge_ids ?? [])]),
    [scenario, selectedStep],
  )
  const nodeLabels = useMemo(
    () => new Map(lifecycle?.nodes.map((node) => [node.id, node.label]) ?? []),
    [lifecycle?.nodes],
  )
  const activeCallLabels = useMemo(
    () => controlSteps.map(stepToEdgeLabelCall).filter((call): call is EdgeLabelCall => call !== null),
    [controlSteps],
  )
  const selectedEndpointNodeIds = useMemo(
    () => new Set([selectedStep?.from, selectedStep?.to].filter((id): id is string => Boolean(id))),
    [selectedStep],
  )

  function handleEdgeSelect(edgeId: string) {
    const matchingSteps = controlSteps.filter((item) => item.edge_id === edgeId || item.affected_edge_ids.includes(edgeId))
    const step = selectedStep
      ? matchingSteps.sort((a, b) => Math.abs(a.seq - selectedStep.seq) - Math.abs(b.seq - selectedStep.seq))[0]
      : matchingSteps[0]

    if (step) {
      selectStepAndReveal(step)
    }
  }

  if (!lifecycle || !index || !scenario) {
    return (
      <AsyncBoundary
        loading={error === null}
        error={error}
        loadingLabel="Loading control paths..."
        errorPrefix="Failed to load control paths"
      />
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <SubjectSwitcher
        label="Control path"
        ariaLabel="Control path"
        value={slug}
        options={index.map((item) => ({ value: item.slug, label: item.label }))}
        onChange={handleSlugChange}
      />
      <div className="lifecycle-workspace">
        <Card>
          <CardHeader>
            <CardTitle>{scenario.label}</CardTitle>
            <p className="text-sm text-ink-soft">{scenario.summary}</p>
            <div className="guide-hack-panel compact">
              <a
                className="guide-action"
                href={guideUrl(scenario.guide_anchor)}
                target="_blank"
                rel="noopener noreferrer"
              >
                <BookOpen size={13} aria-hidden="true" />
                <span>{scenario.guide_title}</span>
              </a>
              <div className="guide-command">
                <Terminal size={13} aria-hidden="true" />
                <code>python {scenario.hack_script}</code>
              </div>
              <p className="text-xs text-ink-soft">{scenario.hack_summary}</p>
            </div>
          </CardHeader>
          <CardContent>
            <div className="control-main lifecycle-main">
              <div className="control-sequence-shell lifecycle-sequence">
                <ControlSequence
                  steps={controlSteps}
                  nodeLabels={nodeLabels}
                  selectedStepId={selectedStep?.id ?? null}
                  onSelect={selectStep}
                  registerStepRow={registerStepRow}
                />
              </div>
              <div className="control-diagram-shell lifecycle-diagram">
                <LifecycleDiagram
                  nodes={lifecycle.nodes}
                  edges={lifecycle.edges}
                  activeNodeIds={activeNodeIds}
                  activeEdgeIds={activeEdgeIds}
                  selectedId={selectedNode?.id ?? null}
                  selectedEdgeId={selectedStep?.edge_id ?? null}
                  selectedCallFrom={selectedStep?.from ?? null}
                  selectedCallTo={selectedStep?.to ?? null}
                  selectedCall={selectedCall}
                  activeCallLabels={activeCallLabels}
                  activePhaseId="control-path"
                  selectedEndpointNodeIds={selectedEndpointNodeIds}
                  onSelect={(node) => setSelected({ type: 'node', node })}
                  onSelectEdge={handleEdgeSelect}
                />
              </div>
            </div>
          </CardContent>
        </Card>
        <div className="lifecycle-drawer-shell">
          <LifecycleDrawer selection={selected} phase={null} nodeLabels={nodeLabels} />
        </div>
      </div>
    </div>
  )
}
