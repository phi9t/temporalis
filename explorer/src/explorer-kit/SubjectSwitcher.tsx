import { cn } from '@/lib/utils'

export function SubjectSwitcher<T extends string>({
  label,
  value,
  options,
  onChange,
  ariaLabel,
}: {
  label?: string
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  ariaLabel?: string
}) {
  const useSelect = options.length > 6

  return (
    <div className="flex flex-wrap items-center gap-2">
      {label && <span className="subject-switcher-label">{label}</span>}
      {useSelect ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as T)}
          aria-label={ariaLabel}
          className="subject-select"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ) : (
        <div className="flex flex-wrap gap-2" aria-label={ariaLabel}>
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              aria-pressed={value === opt.value}
              onClick={() => onChange(opt.value)}
              className={cn('view-tab', value === opt.value && 'view-tab--active')}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
