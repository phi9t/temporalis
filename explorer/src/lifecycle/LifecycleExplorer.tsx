import { useEffect, useMemo, useState } from 'react'
import { AsyncBoundary } from '@/explorer-kit/AsyncBoundary'
import { SubjectSwitcher } from '@/explorer-kit/SubjectSwitcher'
import { ViewTabs } from '@/explorer-kit/ViewTabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'
import { errorMessage, fetchExplorerJson } from '@/lib/fetch'
import LifecycleDiagram from './LifecycleDiagram'
import LifecycleDrawer from './LifecycleDrawer'
import type { LifecycleManifest, LifecycleNode } from './types'

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
  const [manifestError, setManifestError] = useState<string | null>(null)
  const [phaseId, setPhaseId] = useState<string>('')
  const [selected, setSelected] = useState<LifecycleNode | null>(null)

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

        setManifest(loaded)
        setPhaseId(loaded.phases[0]?.id ?? '')
        setSelected(null)
      })
      .catch((error: unknown) => {
        if (!isCurrent) return

        setManifestError(errorMessage(error))
      })

    return () => {
      isCurrent = false
    }
  }, [entry])

  function handleSlugChange(nextSlug: string) {
    setSlug(nextSlug)
    setManifest(null)
    setManifestError(null)
    setSelected(null)
  }

  const phase = manifest?.phases.find((item) => item.id === phaseId) ?? manifest?.phases[0] ?? null
  const activeNodeIds = useMemo(() => new Set(phase?.node_ids ?? []), [phase])
  const activeEdgeIds = useMemo(() => {
    if (!manifest) return new Set<string>()

    return new Set(
      manifest.edges
        .filter((edge) => activeNodeIds.has(edge.from) || activeNodeIds.has(edge.to))
        .map((edge) => edge.id),
    )
  }, [activeNodeIds, manifest])

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
          onChange={setPhaseId}
          options={manifest.phases.map((item) => ({ value: item.id, label: item.label }))}
        />
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
        <Card>
          <CardHeader>
            <CardTitle>{phase?.label ?? manifest.label}</CardTitle>
            <p className="text-sm text-ink-soft">{phase?.summary}</p>
          </CardHeader>
          <CardContent>
            <LifecycleDiagram
              nodes={manifest.nodes}
              edges={manifest.edges}
              activeNodeIds={activeNodeIds}
              activeEdgeIds={activeEdgeIds}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          </CardContent>
        </Card>
        <div className="xl:sticky xl:top-6">
          <LifecycleDrawer node={selected} phase={phase} />
        </div>
      </div>
    </div>
  )
}
