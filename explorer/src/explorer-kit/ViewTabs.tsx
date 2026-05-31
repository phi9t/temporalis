import { cn } from '@/lib/utils'

export function ViewTabs<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  ariaLabel?: string
}) {
  return (
    <div className="flex flex-wrap gap-2" aria-label={ariaLabel}>
      {options.map(({ value: v, label }) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={cn(
            'rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors',
            value === v
              ? 'border-panelborder-active bg-panel-hover text-ink'
              : 'border-panelborder bg-panel text-ink-soft hover:text-ink',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
