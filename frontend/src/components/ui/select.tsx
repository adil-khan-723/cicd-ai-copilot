import * as React from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SelectOption {
  value: string
  label: string
  hint?: string  // optional secondary text shown right of label
}

export interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  label?: string
  className?: string
  triggerClassName?: string
  size?: 'sm' | 'md'
  align?: 'left' | 'right'  // menu alignment
}

/**
 * Styled dropdown matching Input aesthetic. Replaces native <select> for visual
 * consistency. Click-outside / Esc dismisses. Keyboard: ↑/↓ navigate, Enter/Space select.
 */
export function Select({
  value,
  onChange,
  options,
  placeholder = 'Select…',
  disabled,
  label,
  className,
  triggerClassName,
  size = 'md',
  align = 'left',
}: SelectProps) {
  const [open, setOpen] = React.useState(false)
  const [focusIndex, setFocusIndex] = React.useState(0)
  const ref = React.useRef<HTMLDivElement>(null)

  const selected = options.find(o => o.value === value)
  const heightCls = size === 'sm' ? 'h-8 text-[12px]' : 'h-9 text-sm'

  // Close on click-outside
  React.useEffect(() => {
    if (!open) return
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  // Sync focus to current value when opening
  React.useEffect(() => {
    if (open) {
      const i = options.findIndex(o => o.value === value)
      setFocusIndex(i >= 0 ? i : 0)
    }
  }, [open, value, options])

  function handleKey(e: React.KeyboardEvent) {
    if (disabled) return
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault()
        setOpen(true)
      }
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusIndex(i => (i + 1) % options.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusIndex(i => (i - 1 + options.length) % options.length)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      const opt = options[focusIndex]
      if (opt) {
        onChange(opt.value)
        setOpen(false)
      }
    }
  }

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label && (
        <label className="text-[10px] font-medium text-text-muted uppercase tracking-widest">
          {label}
        </label>
      )}
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => !disabled && setOpen(o => !o)}
          onKeyDown={handleKey}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={cn(
            'flex w-full items-center justify-between gap-2 rounded-md border border-glass bg-surface px-3 text-text-primary',
            'font-mono transition-all duration-150 cursor-pointer',
            'hover:border-accent/30',
            'focus:outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/20 focus:bg-card',
            'disabled:cursor-not-allowed disabled:opacity-40',
            open && 'border-accent/40 ring-2 ring-accent/20 bg-card',
            heightCls,
            triggerClassName,
          )}
        >
          <span className={cn('truncate text-left', !selected && 'text-text-dim')}>
            {selected ? selected.label : placeholder}
          </span>
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 shrink-0 text-text-muted transition-transform duration-150',
              open && 'rotate-180',
            )}
            strokeWidth={2}
          />
        </button>

        {open && (
          <div
            role="listbox"
            className={cn(
              'absolute z-50 mt-1 w-full min-w-[180px] overflow-hidden rounded-md border border-glass bg-card shadow-modal',
              'animate-in fade-in-0 zoom-in-95 duration-100',
              align === 'right' && 'right-0',
            )}
          >
            <div className="max-h-[260px] overflow-y-auto py-1">
              {options.length === 0 ? (
                <div className="px-3 py-2 text-[12px] font-mono text-text-dim">No options</div>
              ) : (
                options.map((opt, i) => {
                  const isSelected = opt.value === value
                  const isFocused = i === focusIndex
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onMouseEnter={() => setFocusIndex(i)}
                      onClick={() => { onChange(opt.value); setOpen(false) }}
                      className={cn(
                        'flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-[12px] font-mono transition-colors',
                        'cursor-pointer',
                        isFocused && 'bg-accent/10 text-text-primary',
                        !isFocused && 'text-text-base',
                        isSelected && 'text-accent',
                      )}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        {isSelected && <Check className="h-3 w-3 shrink-0" strokeWidth={2.5} />}
                        <span className={cn('truncate', !isSelected && 'pl-5')}>{opt.label}</span>
                      </span>
                      {opt.hint && (
                        <span className="text-[10px] text-text-dim font-mono shrink-0">{opt.hint}</span>
                      )}
                    </button>
                  )
                })
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
