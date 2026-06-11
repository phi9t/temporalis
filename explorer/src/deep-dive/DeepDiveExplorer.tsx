import { useCallback, useEffect, useMemo, useState } from 'react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { ViewTabs } from '@/explorer-kit/ViewTabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import FlowDiagram, { controlStepToFlowItem, lifecycleCallToFlowItem } from '@/lifecycle/FlowDiagram'
import { getSortedLifecycleCalls } from '@/lifecycle/manifestValidation'
import type { ControlScenario, ControlStep, LifecycleCall, LifecycleManifest, LifecycleNode } from '@/lifecycle/types'

type DeepDiveTrack = 'lifecycle' | 'control'

interface LifecycleEntry {
  slug: string
  label: string
  manifest: string
}

interface ControlEntry {
  slug: string
  label: string
  manifest: string
}

const TRACK_OPTIONS: Array<{ value: DeepDiveTrack; label: string }> = [
  { value: 'lifecycle', label: 'Lifecycle' },
  { value: 'control', label: 'Control Paths' },
]

export default function DeepDiveExplorer(_props: ExplorerModeProps) {
  const [track, setTrack] = useState<DeepDiveTrack>('lifecycle')

  const [lifecycleIndex, setLifecycleIndex] = useState<LifecycleEntry[] | null>(null)
  const [lifecycleSlug, setLifecycleSlug] = useState<string>('')
  const [lifecycleManifest, setLifecycleManifest] = useState<LifecycleManifest | null>(null)
  const [lifecycleCalls, setLifecycleCalls] = useState<LifecycleCall[]>([])
  const [lifecyclePhaseId, setLifecyclePhaseId] = useState<string>('')
  const [selectedLifecycleCall, setSelectedLifecycleCall] = useState<LifecycleCall | null>(null)
  const [selectedLifecycleNode, setSelectedLifecycleNode] = useState<LifecycleNode | null>(null)
  const [lifecycleError, setLifecycleError] = useState<string | null>(null)

  const [controlLifecycle, setControlLifecycle] = useState<LifecycleManifest | null>(null)
  const [controlIndex, setControlIndex] = useState<ControlEntry[] | null>(null)
  const [controlSlug, setControlSlug] = useState<string>('')
  const [controlScenario, setControlScenario] = useState<ControlScenario | null>(null)
  const [selectedControlStep, setSelectedControlStep] = useState<ControlStep | null>(null)
  const [selectedControlNode, setSelectedControlNode] = useState<LifecycleNode | null>(null)
  const [controlError, setControlError] = useState<string | null>(null)

  const selectLifecycleCall = useCallback((call: LifecycleCall) => {
    setLifecyclePhaseId(call.phase_id)
    setSelectedLifecycleCall(call)
    setSelectedLifecycleNode(null)
  }, [])

  useEffect(() => {
    fetchExplorerJson<LifecycleEntry[]>('lifecycle/index.json')
      .then((entries) => {
        setLifecycleIndex(entries)
        setLifecycleSlug(entries[0]?.slug ?? '')
      })
      .catch((error: unknown) => setLifecycleError(errorMessage(error)))
  }, [])

  const lifecycleEntry = lifecycleIndex?.find((item) => item.slug === lifecycleSlug) ?? null

  useEffect(() => {
    if (!lifecycleEntry) return

    let isCurrent = true

    fetchExplorerJson<LifecycleManifest>(lifecycleEntry.manifest)
      .then((loaded) => {
        if (!isCurrent) return

        const sortedCalls = getSortedLifecycleCalls(loaded)

        setLifecycleManifest(loaded)
        setLifecycleCalls(sortedCalls)
        setLifecyclePhaseId(sortedCalls[0]?.phase_id ?? loaded.phases[0]?.id ?? '')
        setSelectedLifecycleCall(sortedCalls[0] ?? null)
        setSelectedLifecycleNode(null)
      })
      .catch((error: unknown) => {
        if (!isCurrent) return
        setLifecycleError(errorMessage(error))
      })

    return () => {
      isCurrent = false
    }
  }, [lifecycleEntry])

  useEffect(() => {
    let isCurrent = true

    Promise.all([
      fetchExplorerJson<LifecycleManifest>('lifecycle/kilvin-asyncio-happy-path.json'),
      fetchExplorerJson<ControlEntry[]>('control-paths/index.json'),
    ])
      .then(([loadedLifecycle, loadedIndex]) => {
        if (!isCurrent) return

        setControlLifecycle(loadedLifecycle)
        setControlIndex(loadedIndex)
        setControlSlug(loadedIndex[0]?.slug ?? '')
      })
      .catch((error: unknown) => {
        if (!isCurrent) return
        setControlError(errorMessage(error))
      })

    return () => {
      isCurrent = false
    }
  }, [])

  const controlEntry = controlIndex?.find((item) => item.slug === controlSlug) ?? null

  useEffect(() => {
    if (!controlEntry) return

    let isCurrent = true

    fetchExplorerJson<ControlScenario>(controlEntry.manifest)
      .then((loaded) => {
        if (!isCurrent) return

        const sortedSteps = [...loaded.steps].sort((a, b) => a.seq - b.seq)

        setControlScenario(loaded)
        setSelectedControlStep(sortedSteps[0] ?? null)
        setSelectedControlNode(null)
      })
      .catch((error: unknown) => {
        if (!isCurrent) return
        setControlError(errorMessage(error))
      })

    return () => {
      isCurrent = false
    }
  }, [controlEntry])

  function handleLifecycleSlugChange(nextSlug: string) {
    setLifecycleSlug(nextSlug)
    setLifecycleManifest(null)
    setLifecycleCalls([])
    setLifecycleError(null)
    setSelectedLifecycleCall(null)
    setSelectedLifecycleNode(null)
  }

  function handleLifecyclePhaseChange(nextPhaseId: string) {
    const call = lifecycleCalls.find((item) => item.phase_id === nextPhaseId)

    if (call) {
      selectLifecycleCall(call)
      return
    }

    setLifecyclePhaseId(nextPhaseId)
    setSelectedLifecycleCall(null)
    setSelectedLifecycleNode(null)
  }

  function handleControlSlugChange(nextSlug: string) {
    setControlSlug(nextSlug)
    setControlScenario(null)
    setControlError(null)
    setSelectedControlStep(null)
    setSelectedControlNode(null)
  }

  const lifecyclePhase =
    lifecycleManifest?.phases.find((item) => item.id === lifecyclePhaseId) ?? lifecycleManifest?.phases[0] ?? null
  const activeLifecycleCalls = useMemo(
    () => lifecycleCalls.filter((call) => call.phase_id === (lifecyclePhase?.id ?? '')),
    [lifecycleCalls, lifecyclePhase?.id],
  )
  const lifecycleActiveNodeIds = useMemo(() => {
    const ids = new Set<string>()

    for (const call of activeLifecycleCalls) {
      ids.add(call.from)
      ids.add(call.to)
    }

    return ids
  }, [activeLifecycleCalls])
  const lifecycleFlowItems = useMemo(
    () => activeLifecycleCalls.map(lifecycleCallToFlowItem),
    [activeLifecycleCalls],
  )

  const controlSteps = useMemo(
    () => (controlScenario ? [...controlScenario.steps].sort((a, b) => a.seq - b.seq) : []),
    [controlScenario],
  )
  const controlActiveNodeIds = useMemo(
    () => new Set([...(controlScenario?.highlight_node_ids ?? []), ...(selectedControlStep?.affected_node_ids ?? [])]),
    [controlScenario, selectedControlStep],
  )
  const controlFlowItems = useMemo(
    () => controlSteps.map(controlStepToFlowItem).filter((item): item is NonNullable<typeof item> => item !== null),
    [controlSteps],
  )

  const trackSelector = (
    <ViewTabs
      ariaLabel="Deep dive track"
      value={track}
      onChange={(value) => setTrack(value as DeepDiveTrack)}
      options={TRACK_OPTIONS}
    />
  )

  if (track === 'lifecycle') {
    if (!lifecycleIndex) {
      return (
        <AsyncBoundary
          loading={lifecycleError === null}
          error={lifecycleError}
          loadingLabel="Loading lifecycle index..."
          errorPrefix="Failed to load lifecycle index"
        />
      )
    }

    if (!lifecycleManifest) {
      return (
        <AsyncBoundary
          loading={lifecycleError === null}
          error={lifecycleError}
          loadingLabel="Loading lifecycle manifest..."
          errorPrefix="Failed to load lifecycle manifest"
        />
      )
    }

    return (
      <div className="flex flex-col gap-5">
        <div className="deep-dive-controls">
          {trackSelector}
          <SubjectSwitcher
            label="Lifecycle"
            ariaLabel="Lifecycle subject"
            value={lifecycleSlug}
            options={lifecycleIndex.map((item) => ({ value: item.slug, label: item.label }))}
            onChange={handleLifecycleSlugChange}
          />
          <ViewTabs
            ariaLabel="Lifecycle phase"
            value={lifecyclePhase?.id ?? ''}
            onChange={handleLifecyclePhaseChange}
            options={lifecycleManifest.phases.map((item) => ({ value: item.id, label: item.label }))}
          />
        </div>

        <div className="deep-dive-workspace control-workspace lifecycle-workspace">
          <Card>
            <CardHeader>
              <CardTitle>{lifecyclePhase?.label ?? lifecycleManifest.label}</CardTitle>
              <p className="text-sm text-ink-soft">{lifecyclePhase?.summary}</p>
            </CardHeader>
            <CardContent>
              <div className="control-main control-main--diagram-only lifecycle-main lifecycle-main--diagram-only">
                <div className="control-diagram-shell lifecycle-diagram">
                  <FlowDiagram
                    items={lifecycleFlowItems}
                    nodes={lifecycleManifest.nodes}
                    activeNodeIds={lifecycleActiveNodeIds}
                    selectedNodeId={selectedLifecycleNode?.id ?? null}
                    selectedItemId={selectedLifecycleCall?.id ?? null}
                    onSelectNode={(node) => {
                      setSelectedLifecycleNode(node)
                      setSelectedLifecycleCall(null)
                    }}
                    onSelectItem={(item) => selectLifecycleCall(item.source)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  if (!controlLifecycle || !controlIndex || !controlScenario) {
    return (
      <AsyncBoundary
        loading={controlError === null}
        error={controlError}
        loadingLabel="Loading control paths..."
        errorPrefix="Failed to load control paths"
      />
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="deep-dive-controls">
        {trackSelector}
        <SubjectSwitcher
          label="Control path"
          ariaLabel="Control path"
          value={controlSlug}
          options={controlIndex.map((item) => ({ value: item.slug, label: item.label }))}
          onChange={handleControlSlugChange}
        />
      </div>

      <div className="deep-dive-workspace control-workspace lifecycle-workspace">
        <Card>
          <CardHeader>
            <CardTitle>{controlScenario.label}</CardTitle>
            <p className="text-sm text-ink-soft">{controlScenario.summary}</p>
          </CardHeader>
          <CardContent>
            <div className="control-main control-main--diagram-only lifecycle-main lifecycle-main--diagram-only">
              <div className="control-diagram-shell lifecycle-diagram">
                <FlowDiagram
                  items={controlFlowItems}
                  nodes={controlLifecycle.nodes}
                  activeNodeIds={controlActiveNodeIds}
                  selectedNodeId={selectedControlNode?.id ?? null}
                  selectedItemId={selectedControlStep?.id ?? null}
                  onSelectNode={(node) => {
                    setSelectedControlNode(node)
                    setSelectedControlStep(null)
                  }}
                  onSelectItem={(item) => {
                    setSelectedControlStep(item.source)
                    setSelectedControlNode(null)
                  }}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
