import { motion } from 'framer-motion'
import { Activity, MessageSquare, Server, Settings, Plus, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ActivePanel } from '@/types'

interface SidebarProps {
  active: ActivePanel
  onNav: (panel: ActivePanel) => void
  onNewProject: () => void
}

const navItems: { id: ActivePanel; icon: React.ElementType; label: string }[] = [
  { id: 'pipeline', icon: Activity,      label: 'Pipeline Feed' },
  { id: 'chat',     icon: MessageSquare, label: 'Copilot Chat' },
  { id: 'jobs',     icon: Server,        label: 'Jobs' },
  { id: 'settings', icon: Settings,      label: 'Settings' },
]

export function Sidebar({ active, onNav, onNewProject }: SidebarProps) {
  return (
    <aside className="w-14 flex flex-col items-center py-4 gap-1 border-r border-glass bg-surface shrink-0">
      {/* Logo */}
      <div className="mb-5 flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-accent shadow-glow-accent">
        <Zap className="h-4 w-4 text-white" strokeWidth={2.5} />
      </div>

      {/* Nav */}
      <div className="flex flex-col gap-0.5 flex-1">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onNav(id)}
            title={label}
            className={cn(
              'relative flex h-9 w-9 items-center justify-center rounded-md transition-all duration-150 group cursor-pointer',
              active === id
                ? 'text-white'
                : 'text-text-dim hover:text-text-muted hover:bg-white/5'
            )}
          >
            {active === id && (
              <motion.div
                layoutId="sidebar-active"
                className="absolute inset-0 rounded-md bg-accent-dim border border-accent/25"
                transition={{ type: 'spring', stiffness: 500, damping: 35 }}
              />
            )}
            <Icon
              className={cn(
                'h-4 w-4 relative z-10 transition-colors duration-150',
                active === id ? 'text-accent-hi' : ''
              )}
              strokeWidth={active === id ? 2 : 1.5}
            />
          </button>
        ))}
      </div>

      {/* New project */}
      <button
        onClick={onNewProject}
        title="New Project"
        className="flex h-9 w-9 items-center justify-center rounded-md text-text-dim hover:text-text-muted hover:bg-white/5 transition-all duration-150 cursor-pointer"
      >
        <Plus className="h-4 w-4" strokeWidth={1.5} />
      </button>
    </aside>
  )
}
