import { useEffect, useMemo, useState } from 'react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import LifecycleDiagram from '@/lifecycle/LifecycleDiagram'
import LifecycleDrawer from '@/lifecycle/LifecycleDrawer'
import type { ControlScenario, LifecycleManifest, LifecycleNode } from '@/lifecycle/types'

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
  const [selected, setSelected] = useState<LifecycleNode | null>(null)

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

  useEffect(() => {
    if (!entry) return

    let isCurrent = true

    setScenario(null)
    setError(null)
    setSelected(null)
    fetchExplorerJson<ControlScenario>(entry.manifest)
      .then((loaded) => {
        if (!isCurrent) return

        setScenario(loaded)
      })
      .catch((err: unknown) => {
        if (!isCurrent) return

        setError(errorMessage(err))
      })

    return () => {
      isCurrent = false
    }
  }, [entry])

  const activeNodeIds = useMemo(() => new Set(scenario?.highlight_node_ids ?? []), [scenario])
  const activeEdgeIds = useMemo(() => new Set(scenario?.highlight_edge_ids ?? []), [scenario])

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
        onChange={setSlug}
      />
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
        <Card>
          <CardHeader>
            <CardTitle>{scenario.label}</CardTitle>
            <p className="text-sm text-ink-soft">{scenario.summary}</p>
          </CardHeader>
          <CardContent>
            <LifecycleDiagram
              nodes={lifecycle.nodes}
              edges={lifecycle.edges}
              activeNodeIds={activeNodeIds}
              activeEdgeIds={activeEdgeIds}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          </CardContent>
        </Card>
        <div className="xl:sticky xl:top-6">
          <LifecycleDrawer node={selected} phase={null} />
        </div>
      </div>
    </div>
  )
}
