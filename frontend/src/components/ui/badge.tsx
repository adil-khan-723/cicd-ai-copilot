import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-mono font-medium tracking-wide transition-colors',
  {
    variants: {
      variant: {
        default:  'bg-white/8 text-text-primary border border-glass',
        success:  'bg-success-dim text-success border border-success/15',
        error:    'bg-error-dim text-error border border-error/15',
        warning:  'bg-warning-dim text-warning border border-warning/15',
        info:     'bg-info-dim text-info border border-info/15',
        running:  'bg-running-dim text-running border border-running/15',
        accent:   'bg-accent-dim text-accent border border-accent/20',
        muted:    'bg-white/5 text-text-muted border border-glass',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
