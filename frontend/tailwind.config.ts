import type { Config } from 'tailwindcss'

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Base surfaces — warm cream
        bg:             '#fdf8f5',
        surface:        '#fffcfa',
        card:           '#ffffff',
        'card-hi':      '#fff7f4',
        overlay:        '#fdeee8',
        sidebar:        '#fff0eb',
        'sidebar-hi':   '#ffe4da',

        // Borders — warm-tinted
        border:         'rgba(180,100,80,0.12)',
        'border-hi':    'rgba(180,100,80,0.2)',
        'border-focus': 'rgba(201,112,106,0.45)',

        // Text — warm slate
        'text-primary': '#1c1410',
        'text-base':    '#3d2c28',
        'text-muted':   '#8c6e68',
        'text-dim':     '#c4a49e',

        // Accent — dusty rose
        accent:         '#c9706a',
        'accent-hi':    '#b85c56',
        'accent-soft':  '#e8948f',
        'accent-dim':   'rgba(201,112,106,0.08)',
        'accent-glow':  'rgba(201,112,106,0.15)',
        'accent-border':'rgba(201,112,106,0.22)',

        // Status — warm-tinted
        success:        '#2d7d5f',
        'success-dim':  'rgba(45,125,95,0.08)',
        'success-border':'rgba(45,125,95,0.22)',
        error:          '#c0392b',
        'error-dim':    'rgba(192,57,43,0.07)',
        'error-border': 'rgba(192,57,43,0.2)',
        warning:        '#b07d2a',
        'warning-dim':  'rgba(176,125,42,0.08)',
        info:           '#2e6da0',
        'info-dim':     'rgba(46,109,160,0.08)',
        running:        '#7b5ea7',
        'running-dim':  'rgba(123,94,167,0.08)',
        'running-border':'rgba(123,94,167,0.22)',
      },
      fontFamily: {
        sans:    ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        display: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono:    ['"DM Mono"', '"Fira Code"', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', '14px'],
        xs:    ['12px', '16px'],
        sm:    ['13px', '18px'],
        base:  ['14px', '20px'],
        md:    ['15px', '22px'],
        lg:    ['16px', '24px'],
        xl:    ['18px', '26px'],
        '2xl': ['22px', '30px'],
        '3xl': ['28px', '36px'],
      },
      borderRadius: {
        sm:      '4px',
        DEFAULT: '8px',
        md:      '10px',
        lg:      '12px',
        xl:      '16px',
        '2xl':   '20px',
        '3xl':   '24px',
        full:    '9999px',
      },
      boxShadow: {
        card:     '0 1px 4px rgba(140,80,60,0.06), 0 0 0 1px rgba(180,100,80,0.09)',
        'card-hi':'0 4px 16px rgba(140,80,60,0.1), 0 0 0 1px rgba(180,100,80,0.12)',
        modal:    '0 24px 64px rgba(100,50,40,0.16), 0 0 0 1px rgba(180,100,80,0.1)',
        input:    '0 0 0 1px rgba(180,100,80,0.12)',
        'input-focus': '0 0 0 3px rgba(201,112,106,0.18)',
        sm:       '0 1px 3px rgba(140,80,60,0.07)',
        soft:     '0 2px 12px rgba(140,80,60,0.08)',
        lifted:   '0 8px 24px rgba(140,80,60,0.1)',
      },
      backgroundImage: {
        'gradient-warm':    'linear-gradient(135deg, #fff0eb 0%, #fdf8f5 100%)',
        'gradient-sidebar': 'linear-gradient(180deg, #fff5f1 0%, #ffeee7 100%)',
        'gradient-accent':  'linear-gradient(135deg, #c9706a, #b85c56)',
        'gradient-card':    'linear-gradient(180deg, #ffffff 0%, #fffcfa 100%)',
        'shimmer':          'linear-gradient(90deg, transparent, rgba(255,255,255,0.7), transparent)',
      },
      animation: {
        'fade-in':   'fadeIn 0.18s ease-out',
        'slide-up':  'slideUp 0.22s cubic-bezier(0.16,1,0.3,1)',
        'pulse-dot': 'pulseDot 2s ease-in-out infinite',
        'shimmer':   'shimmer 1.8s infinite',
      },
      keyframes: {
        fadeIn:   { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp:  { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        pulseDot: { '0%,100%': { opacity: '1', transform: 'scale(1)' }, '50%': { opacity: '0.35', transform: 'scale(0.7)' } },
        shimmer:  { '0%': { backgroundPosition: '-200%' }, '100%': { backgroundPosition: '200%' } },
      },
    },
  },
  plugins: [],
} satisfies Config
