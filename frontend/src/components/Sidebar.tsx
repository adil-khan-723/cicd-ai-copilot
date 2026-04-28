import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Activity, MessageSquare, Server, Settings, Zap, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ActivePanel } from '@/types'

interface SidebarProps {
  active: ActivePanel
  onNav: (panel: ActivePanel) => void
  onNewProject: () => void
  failureCount?: number
}

const navItems: { id: ActivePanel; icon: React.ElementType; label: string; desc: string }[] = [
  { id: 'pipeline', icon: Activity,      label: 'Feed',     desc: 'Live pipeline events' },
  { id: 'chat',     icon: MessageSquare, label: 'Copilot',  desc: 'AI pipeline assistant' },
  { id: 'jobs',     icon: Server,        label: 'Jobs',     desc: 'Jenkins job browser' },
  { id: 'settings', icon: Settings,      label: 'Settings', desc: 'Configure project' },
]

export function Sidebar({ active, onNav, onNewProject: _onNewProject, failureCount = 0 }: SidebarProps) {
  const [stats, setStats] = useState<{ jobs: number; failures: number } | null>(null)
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('devops_ai_sidebar_collapsed') === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem('devops_ai_sidebar_collapsed', String(collapsed))
    } catch {}
  }, [collapsed])

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
    <aside className={cn(
      'flex flex-col border-r border-accent-border/60 sidebar-texture shrink-0 transition-all duration-200',
      collapsed ? 'w-14' : 'w-60'
    )}>

      {/* Logo */}
      <div className={cn('pt-6 pb-5', collapsed ? 'px-2.5' : 'px-5')}>
        <div className={cn('flex items-center', collapsed ? 'justify-center' : 'gap-3')}>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-accent shadow-soft shrink-0">
            <Zap className="h-[18px] w-[18px] text-white" strokeWidth={2.5} />
          </div>
          {!collapsed && (
            <div>
              <p className="text-[15px] font-extrabold text-text-primary tracking-tight leading-none">DevOps AI</p>
              <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">CI/CD Copilot</p>
            </div>
          )}
        </div>
        {!collapsed && (
          <div className="mt-5 h-px bg-gradient-to-r from-accent-border/80 via-accent-border/30 to-transparent" />
        )}
      </div>

      {/* Stats — compact single line */}
      {stats && !collapsed && (
        <div className="mx-4 mb-4 px-3 py-2 rounded-lg border border-accent-border/40 bg-white/60 flex items-center gap-1.5 font-mono text-[11px]">
          <span className="text-text-muted">{stats.jobs} jobs</span>
          <span className="text-text-dim">·</span>
          <span className={stats.failures > 0 ? 'text-error font-semibold' : 'text-success'}>
            {stats.failures} failing
          </span>
        </div>
      )}

      {/* Nav label */}
      {!collapsed && (
        <p className="px-5 mb-2 text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.16em]">
          Navigation
        </p>
      )}

      {/* Nav items */}
      <nav className={cn('flex flex-col gap-0.5 flex-1', collapsed ? 'px-1.5' : 'px-3')}>
        {navItems.map(({ id, icon: Icon, label, desc }) => (
          <button
            key={id}
            onClick={() => onNav(id)}
            title={collapsed ? label : undefined}
            className={cn(
              'relative flex items-center gap-3 rounded-xl transition-all duration-150 group text-left cursor-pointer w-full',
              collapsed ? 'justify-center px-0 py-2.5' : 'px-3 py-2.5',
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
            {active === id && !collapsed && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-accent" />
            )}

            <div className="relative z-10 shrink-0">
              <Icon
                className={cn(
                  'h-4 w-4 transition-colors duration-150',
                  active === id ? 'text-accent' : 'text-text-dim group-hover:text-text-muted'
                )}
                strokeWidth={active === id ? 2.25 : 1.75}
              />
              {/* Failure badge — icon mode */}
              {id === 'pipeline' && failureCount > 0 && collapsed && (
                <span className="absolute -top-1.5 -right-1.5 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-error text-white text-[9px] font-mono font-semibold px-0.5 leading-none">
                  {failureCount > 99 ? '99+' : failureCount}
                </span>
              )}
            </div>

            {!collapsed && (
              <div className="relative z-10 flex-1 min-w-0 flex items-center gap-1.5">
                <div className="flex-1 min-w-0">
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
                {/* Failure badge — expanded mode */}
                {id === 'pipeline' && failureCount > 0 && (
                  <span className="relative z-10 flex items-center justify-center rounded-full bg-error text-white text-[10px] font-mono font-semibold px-1.5 py-0.5 leading-none shrink-0">
                    {failureCount > 99 ? '99+' : failureCount}
                  </span>
                )}
              </div>
            )}

            {active === id && !collapsed && (
              <div className="relative z-10 h-1.5 w-1.5 rounded-full bg-accent shrink-0" />
            )}
          </button>
        ))}
      </nav>

      {/* Stack tags */}
      {!collapsed && (
        <div className="mx-4 mb-2 mt-4">
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
      )}

      {/* Collapse toggle */}
      <div className={cn('mb-5 mt-2', collapsed ? 'px-1.5' : 'px-3')}>
        <button
          onClick={() => setCollapsed(v => !v)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'flex items-center justify-center rounded-xl border border-accent-border/40 bg-white/50 hover:bg-white/80 text-text-dim hover:text-text-base transition-all duration-150 cursor-pointer',
            collapsed ? 'w-full py-2' : 'w-full py-2 gap-2'
          )}
        >
          {collapsed
            ? <ChevronRight className="h-3.5 w-3.5" strokeWidth={1.75} />
            : (
              <>
                <ChevronLeft className="h-3.5 w-3.5" strokeWidth={1.75} />
                <span className="text-[11px] font-mono">Collapse</span>
              </>
            )}
        </button>
      </div>
    </aside>
  )
}
