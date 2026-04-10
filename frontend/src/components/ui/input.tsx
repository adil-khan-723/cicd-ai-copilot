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
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider">
            {label}
          </label>
        )}
        <input
          type={type}
          className={cn(
            'h-9 w-full rounded border border-border bg-surface px-3 text-sm text-text-primary placeholder:text-text-dim',
            'focus:outline-none focus:ring-1 focus:ring-white/20 focus:border-white/20',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'font-mono',
            error && 'border-error/50 focus:ring-error/20',
            className
          )}
          ref={ref}
          {...props}
        />
        {hint && !error && (
          <p className="text-xs text-text-dim leading-relaxed">{hint}</p>
        )}
        {error && <p className="text-xs text-error">{error}</p>}
      </div>
    )
  }
)
Input.displayName = 'Input'

export { Input }
