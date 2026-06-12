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
          className={cn('view-tab', value === v && 'view-tab--active')}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
