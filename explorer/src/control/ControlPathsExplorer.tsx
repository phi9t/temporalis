import { useCallback, useEffect, useMemo, useState } from 'react'
import { BookOpen, Terminal } from 'lucide-react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { guideUrl } from '@/lib/assets'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import FlowDiagram, { controlStepToFlowItem } from '@/lifecycle/FlowDiagram'
import LifecycleDrawer from '@/lifecycle/LifecycleDrawer'
import type { ControlScenario, ControlSelection, ControlStep, LifecycleManifest } from '@/lifecycle/types'

interface ControlEntry {
  slug: string
  label: string
  manifest: string
}

export default function ControlPathsExplorer(_props: ExplorerModeProps) {
  const [lifecycle, setLifecycle] = useState<LifecycleManifest | null>(null)
  const [index, setIndex] = useState<ControlEntry[] | null>(null)
  const [slug, setSlug] = useState<string>('')
  const [scenario, setScenario] = useState<ControlScenario | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ControlSelection | null>(null)

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

  const selectStep = useCallback((step: ControlStep) => {
    setSelected({ type: 'control-step', step })
  }, [])

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

  const activeNodeIds = useMemo(
    () => new Set([...(scenario?.highlight_node_ids ?? []), ...(selectedStep?.affected_node_ids ?? [])]),
    [scenario, selectedStep],
  )
  const nodeLabels = useMemo(
    () => new Map(lifecycle?.nodes.map((node) => [node.id, node.label]) ?? []),
    [lifecycle?.nodes],
  )
  const flowItems = useMemo(
    () => controlSteps.map(controlStepToFlowItem).filter((item): item is NonNullable<typeof item> => item !== null),
    [controlSteps],
  )

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
            <div className="control-main control-main--diagram-only lifecycle-main lifecycle-main--diagram-only">
              <div className="control-diagram-shell lifecycle-diagram">
                <FlowDiagram
                  items={flowItems}
                  nodes={lifecycle.nodes}
                  activeNodeIds={activeNodeIds}
                  selectedNodeId={selectedNode?.id ?? null}
                  selectedItemId={selectedStep?.id ?? null}
                  onSelectNode={(node) => setSelected({ type: 'node', node })}
                  onSelectItem={(item) => selectStep(item.source)}
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
