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
}

export function PipelineFeed({ cards, onDismiss, onClearAll, onDiscardJob }: PipelineFeedProps) {
  const [activeJob, setActiveJob] = useState<string>('all')

  // Never show dismissed cards
  const visible = cards.filter(c => !c.dismissed)

  // Pre-group by job — success card always first, then failures newest-first
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

  // Sort groups by most recent activity
  const allGroups = Array.from(jobMap.entries())
    .map(([job, builds]) => ({ job, cards: builds, latest: builds[0].createdAt }))
    .sort((a, b) => b.latest - a.latest)

  const jobs = allGroups.map(g => g.job)
  const groups = activeJob === 'all'
    ? allGroups
    : allGroups.filter(g => g.job === activeJob)

  if (visible.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 select-none">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface border border-glass">
          <Activity className="h-6 w-6 text-text-dim" strokeWidth={1.5} />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-text-muted">Waiting for pipeline events</p>
          <p className="text-xs text-text-dim mt-1">
            Trigger a failure or send a webhook to see analysis here
          </p>
        </div>
        <div className="flex items-center gap-2 mt-1 px-4 py-2.5 rounded-lg border border-glass bg-surface font-mono text-xs text-text-muted">
          <Terminal className="h-3.5 w-3.5 text-text-dim" strokeWidth={1.5} />
          <span>POST /webhook/pipeline-failure</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── Toolbar ───────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-glass shrink-0">
        <span className="text-xs font-mono text-text-muted">
          {visible.length} event{visible.length !== 1 ? 's' : ''}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClearAll}
          className="gap-1.5 text-text-dim hover:text-error text-xs"
        >
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
          Clear all
        </Button>
      </div>

      {/* ── Job tabs ──────────────────────────────────────────── */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-glass shrink-0 overflow-x-auto scrollbar-none">
        <JobTab
          label="All"
          count={visible.length}
          active={activeJob === 'all'}
          onClick={() => setActiveJob('all')}
        />
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

      {/* ── Feed ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <div className="flex flex-col gap-4 p-4">
          <AnimatePresence initial={false}>
            {groups.map(group => (
              <motion.div
                key={`group-${group.job}`}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                className="flex flex-col gap-2"
              >
                {/* Job group header — only in All view */}
                {activeJob === 'all' && (
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-semibold text-text-dim uppercase tracking-widest">
                      {group.job}
                    </span>
                    <div className="flex-1 h-px bg-glass" />
                    <span className="text-[10px] font-mono text-text-dim">
                      {group.cards.length} build{group.cards.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                )}

                {/* Build cards — success card renders with Discard button */}
                <div className="flex flex-col gap-2">
                  <AnimatePresence initial={false}>
                    {group.cards.map(card =>
                      card.successEvent
                        ? <SuccessBuildCard
                            key={card.key}
                            card={card}
                            onDiscard={() => onDiscardJob(card.job)}
                          />
                        : <BuildCard key={card.key} card={card} onDismiss={onDismiss} />
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

// ── Job tab pill ───────────────────────────────────────────────────────────────

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
        'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono whitespace-nowrap',
        'border transition-all duration-150 shrink-0 cursor-pointer',
        active
          ? 'border-accent/40 bg-accent/10 text-accent'
          : 'border-glass bg-surface/40 text-text-dim hover:text-text-muted hover:border-glass/80',
      )}
    >
      {label !== 'All' && (
        <span className={cn(
          'h-1.5 w-1.5 rounded-full shrink-0',
          passed ? 'bg-success' : 'bg-error',
        )} />
      )}
      <span>{label}</span>
      <span className={cn(
        'ml-0.5 rounded-full px-1.5 py-0.5 text-[10px] leading-none',
        active ? 'bg-accent/20 text-accent' : 'bg-glass text-text-dim',
      )}>
        {count}
      </span>
    </button>
  )
}
