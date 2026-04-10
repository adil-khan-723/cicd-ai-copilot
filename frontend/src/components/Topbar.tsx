import { GitBranch, Circle } from 'lucide-react'
import type { ActivePanel } from '@/types'

const PANEL_LABELS: Record<ActivePanel, string> = {
  pipeline: 'Pipeline Feed',
  chat: 'Copilot Chat',
  jobs: 'Jobs',
  settings: 'Settings',
}

interface TopbarProps {
  activePanel: ActivePanel
  repoName: string
  jenkinsStatus: 'connected' | 'disconnected' | 'unknown'
}

export function Topbar({ activePanel, repoName, jenkinsStatus }: TopbarProps) {
  return (
    <header className="h-11 flex items-center justify-between px-4 border-b border-border bg-surface shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-text-primary">
          {PANEL_LABELS[activePanel]}
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Repo chip */}
        {repoName && (
          <div className="flex items-center gap-1.5 text-xs text-text-muted font-mono">
            <GitBranch className="h-3 w-3" />
            <span>{repoName}</span>
          </div>
        )}

        {/* Jenkins status */}
        <div className="flex items-center gap-1.5 text-xs text-text-dim">
          <Circle
            className={
              jenkinsStatus === 'connected'
                ? 'h-2 w-2 fill-success text-success'
                : 'h-2 w-2 fill-text-dim text-text-dim'
            }
          />
          <span className="font-mono">jenkins</span>
        </div>
      </div>
    </header>
  )
}
