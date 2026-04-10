import { GitBranch } from 'lucide-react'
import type { ActivePanel } from '@/types'

const PANEL_LABELS: Record<ActivePanel, string> = {
  pipeline: 'Pipeline Feed',
  chat:     'Copilot Chat',
  jobs:     'Jobs',
  settings: 'Settings',
}

interface TopbarProps {
  activePanel:    ActivePanel
  repoName:       string
  jenkinsStatus:  'connected' | 'disconnected' | 'unknown'
}

export function Topbar({ activePanel, repoName, jenkinsStatus }: TopbarProps) {
  return (
    <header className="h-11 flex items-center justify-between px-4 border-b border-glass glass shrink-0">
      <span className="text-sm font-medium text-text-primary tracking-tight">
        {PANEL_LABELS[activePanel]}
      </span>

      <div className="flex items-center gap-4">
        {repoName && (
          <div className="flex items-center gap-1.5 text-[11px] text-text-muted font-mono">
            <GitBranch className="h-3 w-3 text-text-dim" />
            <span>{repoName}</span>
          </div>
        )}

        <div className="flex items-center gap-1.5 text-[11px] font-mono text-text-dim">
          <span
            className={[
              'h-1.5 w-1.5 rounded-full',
              jenkinsStatus === 'connected'
                ? 'bg-success shadow-glow-success dot-pulse'
                : jenkinsStatus === 'disconnected'
                ? 'bg-error'
                : 'bg-text-dim',
            ].join(' ')}
          />
          <span className={jenkinsStatus === 'connected' ? 'text-text-muted' : ''}>jenkins</span>
        </div>
      </div>
    </header>
  )
}
