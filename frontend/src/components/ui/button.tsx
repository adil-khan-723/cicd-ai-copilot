import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded font-medium',
    'text-sm transition-all duration-150 cursor-pointer select-none',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50',
    'disabled:pointer-events-none disabled:opacity-35',
    'active:scale-[0.97]',
  ].join(' '),
  {
    variants: {
      variant: {
        default: [
          'bg-gradient-accent text-white shadow-glow-accent',
          'hover:brightness-110 hover:shadow-[0_0_24px_rgba(99,102,241,0.35)]',
        ].join(' '),
        ghost: [
          'text-text-muted hover:text-text-primary',
          'hover:bg-white/5',
        ].join(' '),
        outline: [
          'border border-glass text-text-primary',
          'hover:bg-white/5 hover:border-glass-hi',
        ].join(' '),
        destructive: [
          'bg-error-dim text-error border border-error/20',
          'hover:bg-error/20',
        ].join(' '),
        success: [
          'bg-success-dim text-success border border-success/20',
          'hover:bg-success/20 hover:shadow-glow-success',
        ].join(' '),
        secondary: [
          'bg-card text-text-primary border border-glass',
          'hover:bg-card-hi hover:border-glass-hi',
        ].join(' '),
        link: 'text-accent hover:text-accent-hi underline-offset-4 hover:underline p-0 h-auto',
      },
      size: {
        default:   'h-8 px-3 py-1.5 text-sm',
        sm:        'h-7 px-2.5 text-xs',
        lg:        'h-10 px-5 text-sm',
        icon:      'h-8 w-8',
        'icon-sm': 'h-7 w-7',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
