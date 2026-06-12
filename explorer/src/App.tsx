import { useCallback, useState } from 'react'
import { ArrowLeft, ArrowRight, Route, Workflow } from 'lucide-react'
import { REPO_HOME, logoMarkUrl } from './lib/assets'
import type { ExplorerMode, NavigateOptions } from './explorer-kit/mode'
import BasicsExplorer from './basics/BasicsExplorer'
import DeepDiveExplorer from './deep-dive/DeepDiveExplorer'

const MODES: ExplorerMode[] = [
  {
    id: 'basics',
    label: 'Basics',
    icon: Workflow,
    subtitle: 'Workflows, activities, task queues, history, workers, retry, and replay in plain language',
    View: BasicsExplorer,
  },
  {
    id: 'deep-dive',
    label: 'Deep Dive',
    icon: Route,
    subtitle: 'Lifecycle, control paths, and the kilvin workflow internals with source-backed inspection',
    View: DeepDiveExplorer,
  },
]

const LEARNING_PATH_HINTS: Record<string, string> = {
  basics: 'Start here: one training run told in plain language.',
  'deep-dive': 'Follow the same run through Temporal internals, the kilvin business logic, and source-backed probes.',
}

export default function App() {
  const [activeId, setActiveId] = useState<string>(MODES[0].id)
  const [navContext, setNavContext] = useState<NavigateOptions | null>(null)
  const navigate = useCallback((id: string, options?: NavigateOptions) => {
    setNavContext(options ?? null)
    setActiveId(id)
    window.scrollTo({ top: 0 })
  }, [])

  const activeIndex = Math.max(
    MODES.findIndex((m) => m.id === activeId),
    0,
  )
  const active = MODES[activeIndex]
  const ActiveView = active.View
  const previousMode = activeIndex > 0 ? MODES[activeIndex - 1] : null
  const nextMode = activeIndex < MODES.length - 1 ? MODES[activeIndex + 1] : null

  return (
    <div className="relative min-h-screen">
      <div className="observatory-bg" aria-hidden="true" />
      <div className="explorer-container">
        <header className="explorer-header">
          <div>
            <a href="#main-content" className="skip-link">
              Skip to main content
            </a>
            <a href={REPO_HOME} className="back-home-link" target="_blank" rel="noopener noreferrer">
              <ArrowLeft size={14} aria-hidden="true" />
              <span>phi9t/temporalis</span>
            </a>
            <div className="header-title-row">
              <img src={logoMarkUrl()} alt="" className="header-logo" width={32} height={32} />
              <h1>Temporal Explorer</h1>
            </div>
            <p>{active.subtitle}</p>
          </div>

          <nav className="family-switch" aria-label="Explorer section">
            {MODES.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`family-switch-btn ${activeId === id ? 'active' : ''}`}
                aria-pressed={activeId === id}
                onClick={() => navigate(id)}
              >
                <Icon size={14} aria-hidden="true" />
                {label}
              </button>
            ))}
          </nav>
        </header>

        <main id="main-content">
          <ActiveView navigate={navigate} context={navContext} />
        </main>

        <footer className="learning-path" aria-label="Learning path">
          <div className="learning-path-slot">
            {previousMode ? (
              <button type="button" className="learning-path-button" onClick={() => navigate(previousMode.id)}>
                <ArrowLeft size={14} aria-hidden="true" />
                <span>{previousMode.label}</span>
              </button>
            ) : null}
          </div>
          <p className="learning-path-hint">{LEARNING_PATH_HINTS[active.id]}</p>
          <div className="learning-path-slot learning-path-slot--end">
            {nextMode ? (
              <button type="button" className="learning-path-button" onClick={() => navigate(nextMode.id)}>
                <span>{nextMode.label}</span>
                <ArrowRight size={14} aria-hidden="true" />
              </button>
            ) : null}
          </div>
        </footer>
      </div>
    </div>
  )
}
