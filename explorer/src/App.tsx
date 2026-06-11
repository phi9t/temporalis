import { useState } from 'react'
import { ArrowLeft, BookOpen, Route, Workflow } from 'lucide-react'
import { REPO_HOME, logoMarkUrl } from './lib/assets'
import type { ExplorerMode } from './explorer-kit/mode'
import BasicsExplorer from './basics/BasicsExplorer'
import DeepDiveExplorer from './deep-dive/DeepDiveExplorer'
import GuideExplorer from './guide/GuideExplorer'

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
    subtitle: 'Lifecycle phases and control paths through the same Temporal swimlane',
    View: DeepDiveExplorer,
  },
  {
    id: 'guide',
    label: "Hacker's Guide",
    icon: BookOpen,
    subtitle: 'Temporal internals, code-first - rendered from HACKERS_GUIDE.md',
    View: GuideExplorer,
  },
]

export default function App() {
  const [activeId, setActiveId] = useState<string>(MODES[0].id)
  const active = MODES.find((m) => m.id === activeId) ?? MODES[0]
  const ActiveView = active.View

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
                onClick={() => setActiveId(id)}
              >
                <Icon size={14} aria-hidden="true" />
                {label}
              </button>
            ))}
          </nav>
        </header>

        <main id="main-content">
          <ActiveView navigate={setActiveId} />
        </main>
      </div>
    </div>
  )
}
