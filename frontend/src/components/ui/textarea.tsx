import * as React from 'react'
import { cn } from '@/lib/utils'

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(
        'w-full rounded-md border border-glass bg-surface px-3 py-2.5',
        'text-sm text-text-primary font-mono placeholder:text-text-dim',
        'transition-all duration-150 resize-none',
        'focus:outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/20 focus:bg-card',
        'disabled:cursor-not-allowed disabled:opacity-40',
        className
      )}
      ref={ref}
      {...props}
    />
  )
)
Textarea.displayName = 'Textarea'

export { Textarea }
