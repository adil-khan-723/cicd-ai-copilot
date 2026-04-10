import type { Config } from 'tailwindcss'

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Base surfaces
        bg:             '#030712',   // near-black base
        surface:        '#0c1121',   // dark navy surface
        card:           '#0f172a',   // slate-900 card
        'card-hi':      '#131d34',   // slightly elevated card
        overlay:        '#1e2a45',   // modals / dropdowns

        // Borders
        border:         'rgba(255,255,255,0.07)',
        'border-hi':    'rgba(255,255,255,0.13)',
        'border-focus': 'rgba(99,102,241,0.5)',

        // Text
        'text-primary': '#e2e8f0',   // slate-200
        'text-muted':   '#64748b',   // slate-500
        'text-dim':     '#334155',   // slate-700

        // Accent — indigo
        accent:         '#6366f1',
        'accent-hi':    '#818cf8',
        'accent-glow':  'rgba(99,102,241,0.20)',
        'accent-dim':   'rgba(99,102,241,0.10)',

        // Status
        success:        '#22c55e',
        'success-dim':  'rgba(34,197,94,0.12)',
        'success-hi':   '#4ade80',
        error:          '#ef4444',
        'error-dim':    'rgba(239,68,68,0.12)',
        warning:        '#f59e0b',
        'warning-dim':  'rgba(245,158,11,0.12)',
        info:           '#38bdf8',
        'info-dim':     'rgba(56,189,248,0.10)',
        running:        '#a78bfa',
        'running-dim':  'rgba(167,139,250,0.12)',
      },
      fontFamily: {
        mono: ['"Fira Code"', '"JetBrains Mono"', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        sm:  '4px',
        DEFAULT: '6px',
        md:  '8px',
        lg:  '12px',
        xl:  '16px',
      },
      boxShadow: {
        'glow-accent': '0 0 20px rgba(99,102,241,0.25)',
        'glow-success':'0 0 12px rgba(34,197,94,0.20)',
        'glow-error':  '0 0 12px rgba(239,68,68,0.20)',
        card:          '0 1px 3px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)',
        modal:         '0 24px 64px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.08)',
        input:         '0 0 0 1px rgba(255,255,255,0.07)',
        'input-focus': '0 0 0 2px rgba(99,102,241,0.4)',
      },
      backgroundImage: {
        'gradient-surface': 'linear-gradient(135deg, #0c1121 0%, #030712 100%)',
        'gradient-card':    'linear-gradient(180deg, rgba(255,255,255,0.03) 0%, transparent 100%)',
        'gradient-accent':  'linear-gradient(135deg, #6366f1, #8b5cf6)',
        'gradient-success': 'linear-gradient(135deg, #22c55e, #16a34a)',
        'shimmer':          'linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)',
      },
      animation: {
        'fade-in':     'fadeIn 0.15s ease-out',
        'slide-up':    'slideUp 0.2s cubic-bezier(0.16,1,0.3,1)',
        'pulse-glow':  'pulseGlow 2s ease-in-out infinite',
        'shimmer':     'shimmer 1.5s infinite',
      },
      keyframes: {
        fadeIn:    { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp:   { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        pulseGlow: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.5' } },
        shimmer:   { '0%': { backgroundPosition: '-200%' }, '100%': { backgroundPosition: '200%' } },
      },
    },
  },
  plugins: [],
} satisfies Config
