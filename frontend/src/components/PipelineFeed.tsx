import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Terminal, Trash2 } from 'lucide-react'
import { BuildCard, SuccessBuildCard } from './BuildCard'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { BuildCard as BuildCardType } from '@/types'

interface PipelineFeedProps {
  cards:          BuildCardType[]
  onDismiss:      (k: string) => void
  onClearAll:     () => void
  onDiscardJob:   (job: string) => void
  onOpenDetail:   (card: BuildCardType) => void
}

export function PipelineFeed({ cards, onDismiss, onClearAll, onDiscardJob, onOpenDetail }: PipelineFeedProps) {
  const [activeJob, setActiveJob] = useState<string>('all')

  const visible = cards.filter(c => !c.dismissed)

  const jobMap = new Map<string, BuildCardType[]>()
  for (const card of visible) {
    if (!jobMap.has(card.job)) jobMap.set(card.job, [])
    jobMap.get(card.job)!.push(card)
  }
  for (const builds of jobMap.values()) {
    builds.sort((a, b) => {
      if (a.successEvent && !b.successEvent) return -1
      if (!a.successEvent && b.successEvent) return  1
      return b.createdAt - a.createdAt
    })
  }

  const allGroups = Array.from(jobMap.entries())
    .map(([job, builds]) => ({ job, cards: builds, latest: builds[0].createdAt }))
    .sort((a, b) => b.latest - a.latest)

  const jobs   = allGroups.map(g => g.job)
  const groups = activeJob === 'all' ? allGroups : allGroups.filter(g => g.job === activeJob)

  if (visible.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 select-none bg-bg">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white border border-accent-border/50 shadow-soft">
          <Activity className="h-7 w-7 text-text-dim" strokeWidth={1.5} />
        </div>
        <div className="text-center">
          <p className="text-[15px] font-semibold text-text-base">Watching for pipeline events</p>
          <p className="text-[13px] font-mono text-text-muted mt-2 leading-relaxed">
            Trigger a failure or send a webhook to see analysis
          </p>
        </div>
        <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border border-accent-border/40 bg-white font-mono text-[12px] text-text-muted shadow-sm">
          <Terminal className="h-4 w-4 text-text-dim shrink-0" strokeWidth={1.5} />
          <span>POST /webhook/pipeline-failure</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg">

      {/* Toolbar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-accent-border/40 shrink-0 bg-surface">
        <span className="text-[12px] font-mono text-text-muted">
          <span className="text-text-base font-semibold">{visible.length}</span>
          {' '}event{visible.length !== 1 ? 's' : ''} in feed
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClearAll}
          className="gap-2 text-text-muted hover:text-error text-[12px] h-7 px-2.5 font-mono"
        >
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
          Clear all
        </Button>
      </div>

      {/* Job tabs */}
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-accent-border/40 shrink-0 overflow-x-auto scrollbar-none bg-surface/80">
        <JobTab label="All" count={visible.length} active={activeJob === 'all'} onClick={() => setActiveJob('all')} />
        {jobs.map(job => (
          <JobTab
            key={job}
            label={job}
            count={visible.filter(c => c.job === job).length}
            active={activeJob === job}
            passed={visible.some(c => c.job === job && c.successEvent)}
            onClick={() => setActiveJob(activeJob === job ? 'all' : job)}
          />
        ))}
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto">
        <div className="flex flex-col gap-3 p-5">
          <AnimatePresence initial={false}>
            {groups.map(group => (
              <motion.div
                key={`group-${group.job}`}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                className="flex flex-col gap-2.5"
              >
                {activeJob === 'all' && (
                  <div className="flex items-center gap-3 mt-1 first:mt-0">
                    <span className="text-[11px] font-mono font-semibold text-text-muted uppercase tracking-[0.12em]">
                      {group.job}
                    </span>
                    <div className="flex-1 h-px bg-accent-border/30" />
                    <span className="text-[11px] font-mono text-text-dim">
                      {group.cards.length} build{group.cards.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                )}
                <div className="flex flex-col gap-2.5">
                  <AnimatePresence initial={false}>
                    {group.cards.map(card =>
                      card.successEvent
                        ? <SuccessBuildCard key={card.key} card={card} onDiscard={() => onDiscardJob(card.job)} />
                        : <BuildCard key={card.key} card={card} onDismiss={onDismiss} onOpenDetail={onOpenDetail} />
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

interface JobTabProps {
  label:   string
  count:   number
  active:  boolean
  passed?: boolean
  onClick: () => void
}

function JobTab({ label, count, active, passed, onClick }: JobTabProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-[12px] font-mono whitespace-nowrap',
        'border transition-all duration-150 shrink-0 cursor-pointer',
        active
          ? 'border-accent-border bg-white text-accent font-semibold shadow-sm'
          : 'border-accent-border/30 bg-white/40 text-text-muted hover:text-text-base hover:bg-white/70 hover:border-accent-border/60',
      )}
    >
      {label !== 'All' && (
        <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', passed ? 'bg-success' : 'bg-error')} />
      )}
      <span>{label}</span>
      <span className={cn(
        'rounded-full px-1.5 py-0.5 text-[10px] leading-none',
        active ? 'bg-accent-dim text-accent' : 'bg-accent-border/20 text-text-muted',
      )}>
        {count}
      </span>
    </button>
  )
}
