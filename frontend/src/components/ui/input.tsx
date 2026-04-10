import * as React from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  hint?: React.ReactNode
  error?: string
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, hint, error, type, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label className="text-[10px] font-medium text-text-muted uppercase tracking-widest">
            {label}
          </label>
        )}
        <input
          type={type}
          className={cn(
            'h-9 w-full rounded-md border border-glass bg-surface px-3 text-sm text-text-primary',
            'font-mono placeholder:text-text-dim placeholder:font-mono',
            'transition-all duration-150',
            'focus:outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/20 focus:bg-card',
            'disabled:cursor-not-allowed disabled:opacity-40',
            error && 'border-error/40 focus:border-error/60 focus:ring-error/20',
            className
          )}
          ref={ref}
          {...props}
        />
        {hint && !error && (
          <p className="text-[11px] text-text-dim leading-relaxed">{hint}</p>
        )}
        {error && <p className="text-[11px] text-error">{error}</p>}
      </div>
    )
  }
)
Input.displayName = 'Input'

export { Input }
