import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { ViewTabs } from '@/explorer-kit/ViewTabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import CallSequence from './CallSequence'
import LifecycleDiagram from './LifecycleDiagram'
import LifecycleDrawer from './LifecycleDrawer'
import { getSortedLifecycleCalls } from './manifestValidation'
import type { LifecycleCall, LifecycleManifest, LifecycleSelection } from './types'

interface LifecycleEntry {
  slug: string
  label: string
  manifest: string
}

export default function LifecycleExplorer(_props: ExplorerModeProps) {
  const [index, setIndex] = useState<LifecycleEntry[] | null>(null)
  const [indexError, setIndexError] = useState<string | null>(null)
  const [slug, setSlug] = useState<string>('')
  const [manifest, setManifest] = useState<LifecycleManifest | null>(null)
  const [calls, setCalls] = useState<LifecycleCall[]>([])
  const [manifestError, setManifestError] = useState<string | null>(null)
  const [phaseId, setPhaseId] = useState<string>('')
  const [selected, setSelected] = useState<LifecycleSelection | null>(null)
  const [revealRequestId, setRevealRequestId] = useState(0)
  const callRowsRef = useRef(new Map<string, HTMLButtonElement>())
  const pendingRevealCallIdRef = useRef<string | null>(null)

  const selectCall = useCallback((call: LifecycleCall) => {
    pendingRevealCallIdRef.current = null
    setPhaseId(call.phase_id)
    setSelected({ type: 'call', call })
  }, [])

  const registerCallRow = useCallback((callId: string, element: HTMLButtonElement | null) => {
    if (element) {
      callRowsRef.current.set(callId, element)
      return
    }

    callRowsRef.current.delete(callId)
  }, [])

  const selectCallAndReveal = useCallback(
    (call: LifecycleCall) => {
      pendingRevealCallIdRef.current = call.id
      setRevealRequestId((requestId) => requestId + 1)
      setPhaseId(call.phase_id)
      setSelected({ type: 'call', call })
    },
    [],
  )

  useEffect(() => {
    fetchExplorerJson<LifecycleEntry[]>('lifecycle/index.json')
      .then((entries) => {
        setIndex(entries)
        setSlug(entries[0]?.slug ?? '')
      })
      .catch((error: unknown) => setIndexError(errorMessage(error)))
  }, [])

  const entry = index?.find((item) => item.slug === slug) ?? null

  useEffect(() => {
    if (!entry) return

    let isCurrent = true

    fetchExplorerJson<LifecycleManifest>(entry.manifest)
      .then((loaded) => {
        if (!isCurrent) return

        const sortedCalls = getSortedLifecycleCalls(loaded)

        setManifest(loaded)
        setCalls(sortedCalls)
        if (sortedCalls[0]) {
          selectCall(sortedCalls[0])
        } else {
          setPhaseId(loaded.phases[0]?.id ?? '')
          setSelected(null)
        }
      })
      .catch((error: unknown) => {
        if (!isCurrent) return

        setManifestError(errorMessage(error))
      })

    return () => {
      isCurrent = false
    }
  }, [entry, selectCall])

  function handleSlugChange(nextSlug: string) {
    setSlug(nextSlug)
    setManifest(null)
    setCalls([])
    setManifestError(null)
    setSelected(null)
  }

  const phase = manifest?.phases.find((item) => item.id === phaseId) ?? manifest?.phases[0] ?? null
  const activePhaseCalls = useMemo(
    () => calls.filter((call) => call.phase_id === (phase?.id ?? '')),
    [calls, phase?.id],
  )
  const activeNodeIds = useMemo(() => {
    const ids = new Set<string>()

    for (const call of activePhaseCalls) {
      ids.add(call.from)
      ids.add(call.to)
    }

    return ids
  }, [activePhaseCalls])
  const activeEdgeIds = useMemo(() => {
    return new Set(activePhaseCalls.map((call) => call.edge_id))
  }, [activePhaseCalls])
  const nodeLabels = useMemo(
    () => new Map(manifest?.nodes.map((node) => [node.id, node.label]) ?? []),
    [manifest?.nodes],
  )
  const phaseLabels = useMemo(
    () => new Map(manifest?.phases.map((item) => [item.id, item.label]) ?? []),
    [manifest?.phases],
  )
  const selectedCall = selected?.type === 'call' ? selected.call : null
  const selectedNode = selected?.type === 'node' ? selected.node : null

  useEffect(() => {
    const pendingRevealCallId = pendingRevealCallIdRef.current
    if (!pendingRevealCallId || selectedCall?.id !== pendingRevealCallId) return

    pendingRevealCallIdRef.current = null
    callRowsRef.current.get(pendingRevealCallId)?.scrollIntoView({ block: 'nearest', behavior: 'auto' })
  }, [revealRequestId, selectedCall?.id])

  const selectedEndpointNodeIds = useMemo(() => {
    if (!selectedCall) return new Set<string>()

    return new Set([selectedCall.from, selectedCall.to])
  }, [selectedCall])

  function handleEdgeSelect(edgeId: string) {
    const call = activePhaseCalls.find((item) => item.edge_id === edgeId) ?? calls.find((item) => item.edge_id === edgeId)

    if (call) {
      selectCallAndReveal(call)
    }
  }

  function handlePhaseChange(nextPhaseId: string) {
    const call = calls.find((item) => item.phase_id === nextPhaseId)

    if (call) {
      selectCallAndReveal(call)
      return
    }

    setPhaseId(nextPhaseId)
    pendingRevealCallIdRef.current = null
    setSelected(null)
  }

  if (!index) {
    return (
      <AsyncBoundary
        loading={indexError === null}
        error={indexError}
        loadingLabel="Loading lifecycle index..."
        errorPrefix="Failed to load lifecycle index"
      />
    )
  }

  if (!manifest) {
    return (
      <AsyncBoundary
        loading={manifestError === null}
        error={manifestError}
        loadingLabel="Loading lifecycle manifest..."
        errorPrefix="Failed to load lifecycle manifest"
      />
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <SubjectSwitcher
          label="Lifecycle"
          ariaLabel="Lifecycle subject"
          value={slug}
          options={index.map((item) => ({ value: item.slug, label: item.label }))}
          onChange={handleSlugChange}
        />
        <ViewTabs
          ariaLabel="Lifecycle phase"
          value={phase?.id ?? ''}
          onChange={handlePhaseChange}
          options={manifest.phases.map((item) => ({ value: item.id, label: item.label }))}
        />
      </div>
      <div className="lifecycle-workspace">
        <Card>
          <CardHeader>
            <CardTitle>{phase?.label ?? manifest.label}</CardTitle>
            <p className="text-sm text-ink-soft">{phase?.summary}</p>
          </CardHeader>
          <CardContent>
            <div className="lifecycle-main">
              <div className="lifecycle-sequence">
                <CallSequence
                  calls={calls}
                  nodeLabels={nodeLabels}
                  activePhaseId={phase?.id ?? ''}
                  selectedCallId={selectedCall?.id ?? null}
                  onSelect={selectCall}
                  registerCallRow={registerCallRow}
                />
              </div>
              <div className="lifecycle-diagram">
                <LifecycleDiagram
                  nodes={manifest.nodes}
                  edges={manifest.edges}
                  activeNodeIds={activeNodeIds}
                  activeEdgeIds={activeEdgeIds}
                  selectedId={selectedNode?.id ?? null}
                  selectedEdgeId={selectedCall?.edge_id ?? null}
                  selectedCallFrom={selectedCall?.from ?? null}
                  selectedCallTo={selectedCall?.to ?? null}
                  selectedEndpointNodeIds={selectedEndpointNodeIds}
                  onSelect={(node) => setSelected({ type: 'node', node })}
                  onSelectEdge={handleEdgeSelect}
                />
              </div>
            </div>
          </CardContent>
        </Card>
        <div className="lifecycle-drawer-shell">
          <LifecycleDrawer selection={selected} phase={phase} nodeLabels={nodeLabels} phaseLabels={phaseLabels} />
        </div>
      </div>
    </div>
  )
}
