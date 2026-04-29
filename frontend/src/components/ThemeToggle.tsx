import { motion } from 'framer-motion'
import { Sun, Moon } from 'lucide-react'
import type { Theme } from '@/hooks/useTheme'

interface ThemeToggleProps {
  theme: Theme
  toggle: () => void
  size?: 'sm' | 'md'
}

export function ThemeToggle({ theme, toggle, size = 'md' }: ThemeToggleProps) {
  const isDark = theme === 'dark'
  const trackW = size === 'sm' ? 44 : 52
  const trackH = size === 'sm' ? 24 : 28
  const knobSize = size === 'sm' ? 18 : 22
  const knobOff = size === 'sm' ? 3 : 3
  const knobOn  = trackW - knobSize - knobOff

  return (
    <button
      onClick={toggle}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="flex items-center gap-2 cursor-pointer select-none group"
      style={{ background: 'none', border: 'none', padding: 0 }}
    >
      {/* Icon */}
      <motion.div
        key={theme}
        initial={{ opacity: 0, rotate: -30, scale: 0.7 }}
        animate={{ opacity: 1, rotate: 0, scale: 1 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        className="text-text-muted group-hover:text-accent transition-colors"
      >
        {isDark
          ? <Moon  className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} strokeWidth={1.75} />
          : <Sun   className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} strokeWidth={1.75} />
        }
      </motion.div>

      {/* Track */}
      <motion.div
        animate={{ backgroundColor: isDark ? '#3d2420' : '#edddd8' }}
        transition={{ duration: 0.4 }}
        style={{
          width: trackW,
          height: trackH,
          borderRadius: trackH,
          position: 'relative',
          boxShadow: isDark
            ? 'inset 0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(201,112,106,0.2)'
            : 'inset 0 1px 3px rgba(140,80,60,0.15), 0 0 0 1px rgba(180,100,80,0.18)',
          flexShrink: 0,
          cursor: 'pointer',
        }}
      >
        {/* Knob */}
        <motion.div
          animate={{ x: isDark ? knobOn : knobOff }}
          transition={{ type: 'spring', stiffness: 500, damping: 32 }}
          style={{
            position: 'absolute',
            top: knobOff,
            width: knobSize,
            height: knobSize,
            borderRadius: '50%',
            background: isDark
              ? 'linear-gradient(135deg, #c9706a, #b85c56)'
              : 'linear-gradient(135deg, #ffffff, #f5e8e4)',
            boxShadow: isDark
              ? '0 2px 6px rgba(0,0,0,0.4), 0 0 8px rgba(201,112,106,0.3)'
              : '0 2px 6px rgba(140,80,60,0.2)',
          }}
        />
      </motion.div>
    </button>
  )
}
