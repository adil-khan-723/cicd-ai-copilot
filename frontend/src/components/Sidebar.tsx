import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Activity, MessageSquare, Server, Settings, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ActivePanel } from '@/types'

interface SidebarProps {
  active: ActivePanel
  onNav: (panel: ActivePanel) => void
  onNewProject: () => void
}

const navItems: { id: ActivePanel; icon: React.ElementType; label: string; desc: string }[] = [
  { id: 'pipeline', icon: Activity,      label: 'Feed',     desc: 'Live pipeline events' },
  { id: 'chat',     icon: MessageSquare, label: 'Copilot',  desc: 'AI pipeline assistant' },
  { id: 'jobs',     icon: Server,        label: 'Jobs',     desc: 'Jenkins job browser' },
  { id: 'settings', icon: Settings,      label: 'Settings', desc: 'Configure project' },
]

export function Sidebar({ active, onNav, onNewProject: _onNewProject }: SidebarProps) {
  const [stats, setStats] = useState<{ jobs: number; failures: number } | null>(null)

  useEffect(() => {
    fetch('/api/jobs')
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : (data.jobs ?? [])
        const failures = list.filter((j: { status: string }) => j.status === 'failure').length
        setStats({ jobs: list.length, failures })
      })
      .catch(() => {})
  }, [])

  return (
    <aside className="w-60 flex flex-col border-r border-accent-border/60 sidebar-texture shrink-0">

      {/* Logo */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-accent shadow-soft shrink-0">
            <Zap className="h-[18px] w-[18px] text-white" strokeWidth={2.5} />
          </div>
          <div>
            <p className="text-[15px] font-extrabold text-text-primary tracking-tight leading-none">DevOps AI</p>
            <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">CI/CD Copilot</p>
          </div>
        </div>
        <div className="mt-5 h-px bg-gradient-to-r from-accent-border/80 via-accent-border/30 to-transparent" />
      </div>

      {/* Stats strip */}
      {stats && (
        <div className="mx-4 mb-5 rounded-xl overflow-hidden border border-accent-border/50 bg-white/60">
          <div className="grid grid-cols-2 divide-x divide-accent-border/40">
            <div className="px-4 py-3 flex flex-col">
              <p className="text-[10px] font-mono text-text-dim uppercase tracking-[0.14em] leading-none h-3">Jobs</p>
              <p className="text-2xl font-extrabold text-text-primary mt-1.5 leading-none">{stats.jobs}</p>
            </div>
            <div className="px-4 py-3 flex flex-col">
              <p className="text-[10px] font-mono text-text-dim uppercase tracking-[0.14em] leading-none h-3">Failing</p>
              <p className={cn(
                'text-2xl font-extrabold mt-1.5 leading-none',
                stats.failures > 0 ? 'text-error' : 'text-success'
              )}>
                {stats.failures}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Nav label */}
      <p className="px-5 mb-2 text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.16em]">
        Navigation
      </p>

      {/* Nav items */}
      <nav className="flex flex-col gap-0.5 px-3 flex-1">
        {navItems.map(({ id, icon: Icon, label, desc }) => (
          <button
            key={id}
            onClick={() => onNav(id)}
            className={cn(
              'relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 group text-left cursor-pointer w-full',
              active === id ? 'text-text-primary' : 'text-text-muted hover:text-text-base hover:bg-white/50'
            )}
          >
            {active === id && (
              <motion.div
                layoutId="sidebar-pill"
                className="absolute inset-0 rounded-xl bg-white border border-accent-border/60 shadow-sm"
                transition={{ type: 'spring', stiffness: 500, damping: 35 }}
              />
            )}
            {active === id && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-accent" />
            )}

            <Icon
              className={cn(
                'h-4 w-4 relative z-10 shrink-0 transition-colors duration-150',
                active === id ? 'text-accent' : 'text-text-dim group-hover:text-text-muted'
              )}
              strokeWidth={active === id ? 2.25 : 1.75}
            />
            <div className="relative z-10 flex-1 min-w-0">
              <p className={cn(
                'text-[13px] font-semibold leading-none',
                active === id ? 'text-text-primary' : ''
              )}>
                {label}
              </p>
              <p className="text-[11px] font-mono text-text-dim mt-1 leading-none truncate">
                {desc}
              </p>
            </div>
            {active === id && (
              <div className="relative z-10 h-1.5 w-1.5 rounded-full bg-accent shrink-0" />
            )}
          </button>
        ))}
      </nav>

      {/* Stack tags */}
      <div className="mx-4 mb-5 mt-4">
        <div className="rounded-xl border border-accent-border/40 bg-white/50 px-4 py-3">
          <p className="text-[10px] font-mono text-text-dim uppercase tracking-[0.14em] mb-2.5">Stack</p>
          <div className="flex flex-wrap gap-1.5">
            {['Jenkins', 'GitHub', 'Ollama', 'Claude'].map(tag => (
              <span
                key={tag}
                className="text-[10px] font-mono text-text-muted bg-white border border-accent-border/50 rounded-full px-2.5 py-1"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </aside>
  )
}
