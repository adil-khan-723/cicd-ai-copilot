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
  { id: 'pipeline', icon: Activity, label: 'Pipeline Feed' },
  { id: 'chat', icon: MessageSquare, label: 'Copilot Chat' },
  { id: 'jobs', icon: Server, label: 'Jobs' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export function Sidebar({ active, onNav, onNewProject }: SidebarProps) {
  return (
    <aside className="w-14 flex flex-col items-center py-4 gap-1 border-r border-border bg-surface shrink-0">
      {/* Logo */}
      <div className="mb-4 flex h-8 w-8 items-center justify-center rounded bg-white/5 border border-border">
        <Zap className="h-4 w-4 text-white/60" />
      </div>

      <div className="flex flex-col gap-1 flex-1">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onNav(id)}
            title={label}
            className={cn(
              'relative flex h-9 w-9 items-center justify-center rounded transition-colors group',
              active === id
                ? 'bg-white/10 text-text-primary'
                : 'text-text-dim hover:bg-white/5 hover:text-text-muted'
            )}
          >
            {active === id && (
              <motion.div
                layoutId="sidebar-active"
                className="absolute inset-0 rounded bg-white/10"
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              />
            )}
            <Icon className="h-4 w-4 relative z-10" />
          </button>
        ))}
      </div>

      {/* New project */}
      <button
        onClick={onNewProject}
        title="New Project"
        className="flex h-9 w-9 items-center justify-center rounded text-text-dim hover:bg-white/5 hover:text-text-muted transition-colors"
      >
        <Plus className="h-4 w-4" />
      </button>
    </aside>
  )
}
