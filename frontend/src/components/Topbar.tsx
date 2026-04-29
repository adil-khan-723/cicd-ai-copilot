import { GitBranch, Circle, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ActivePanel } from '@/types'

const PANEL_META: Record<ActivePanel, { title: string; sub: string }> = {
  pipeline: { title: 'Pipeline Feed',   sub: 'Live CI/CD event stream' },
  chat:     { title: 'AI Copilot',      sub: 'Pipeline assistant & generator' },
  jobs:     { title: 'Jenkins Jobs',    sub: 'Browse and trigger builds' },
  settings: { title: 'Settings',        sub: 'Project configuration' },
}

interface TopbarProps {
  activePanel:   ActivePanel
  repoName:      string
  jenkinsStatus: 'connected' | 'disconnected' | 'unknown'
}

export function Topbar({ activePanel, repoName, jenkinsStatus }: TopbarProps) {
  const { title, sub } = PANEL_META[activePanel]

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-accent-border/50 bg-surface shrink-0">
      <div>
        <h1 className="text-[16px] font-extrabold text-text-primary leading-none tracking-tight">{title}</h1>
        <p className="text-[11px] font-mono text-text-dim mt-1 leading-none">{sub}</p>
      </div>

      <div className="flex items-center gap-3">
        {repoName && (
          <a
            href={`https://github.com/${repoName}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-[12px] font-mono text-text-muted bg-overlay/60 border border-accent-border/40 rounded-lg px-3 py-1.5 max-w-xs hover:border-accent-border hover:text-accent transition-all duration-150"
          >
            <GitBranch className="h-3.5 w-3.5 text-text-dim shrink-0" />
            <span className="break-all">{repoName}</span>
            <ExternalLink className="h-3 w-3 shrink-0 text-text-dim" strokeWidth={1.5} />
          </a>
        )}

        <div className={cn(
          'flex items-center gap-2 font-mono px-3 py-1.5 rounded-lg border',
          jenkinsStatus === 'connected'
            ? 'text-success border-success-border bg-success-dim text-[12px] font-semibold'
            : jenkinsStatus === 'disconnected'
            ? 'text-error border-error-border bg-error-dim text-[12px] font-semibold'
            : 'text-text-muted border-accent-border/40 bg-overlay/40 text-[12px]'
        )}>
          <Circle className={cn('h-2.5 w-2.5 fill-current shrink-0', jenkinsStatus === 'connected' ? 'dot-pulse' : '')} />
          <span>
            {jenkinsStatus === 'connected'
              ? 'Jenkins Connected'
              : jenkinsStatus === 'disconnected'
              ? 'Disconnected'
              : 'Jenkins'}
          </span>
        </div>
      </div>
    </header>
  )
}
