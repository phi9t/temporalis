import type { ComponentType } from 'react'
import type { LucideIcon } from 'lucide-react'

/**
 * Optional context carried along a cross-view navigation, so one mode can
 * deep-link into a specific spot in another (Basics step → Deep Dive phase,
 * Deep Dive phase → Guide section).
 */
export interface NavigateOptions {
  guideAnchor?: string
  deepDiveTrack?: 'lifecycle' | 'control'
  deepDivePhaseId?: string
  deepDiveScenarioSlug?: string
}

/**
 * Props every Explorer mode view receives from the family-switcher shell.
 * `navigate` lets a mode cross-link to another (e.g. Component → Architecture),
 * which generalizes the old bespoke `onOpenArchitecture` callback (R3 cross-links).
 * `context` is the NavigateOptions payload from the navigation that opened
 * this view, if any.
 */
export interface ExplorerModeProps {
  navigate: (id: string, options?: NavigateOptions) => void
  context?: NavigateOptions | null
}

/**
 * A mode in the family switcher. `App.tsx` holds a typed registry of these and
 * renders the active one, so adding a mode is one array entry — no new conditional.
 *
 * Each `View` is itself the index→manifest reader for its mode (loads
 * `<mode>/index.json` then the per-subject manifest); the contract documents the
 * shared shape rather than hoisting loading into a generic shell.
 */
export interface ExplorerMode {
  id: string
  label: string
  icon: LucideIcon
  subtitle: string
  View: ComponentType<ExplorerModeProps>
}
