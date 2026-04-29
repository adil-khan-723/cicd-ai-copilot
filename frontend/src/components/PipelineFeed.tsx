import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Terminal, Trash2, Zap, ChevronsDownUp, ChevronsUpDown, ArrowDownUp, AlertTriangle } from 'lucide-react'
import { BuildCard, SuccessBuildCard } from './BuildCard'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { BuildCard as BuildCardType } from '@/types'

const DIAGNOSTIC_TYPES = new Set(['diagnostic_only', 'missing_plugin'])
const CONFIDENCE_THRESHOLD = 0.75

type StatusFilter = 'all' | 'analyzing' | 'fixable' | 'manual'
type SortMode = 'newest' | 'failures'

interface PipelineFeedProps {
  cards:                BuildCardType[]
  latestFailingKeys:    Set<string>
  onDismiss:            (k: string) => void
  onClearAll:           () => void
  onDiscardJob:         (job: string) => void
  onOpenDetail:         (card: BuildCardType) => void
  onOpenDetailAtStage?: (card: BuildCardType, stage: string) => void
  isConfigured?:        boolean
  onConfigure?:         () => void
}

export function PipelineFeed({ cards, latestFailingKeys, onDismiss, onClearAll, onDiscardJob, onOpenDetail, onOpenDetailAtStage, isConfigured = true, onConfigure }: PipelineFeedProps) {
  const [activeJob,      setActiveJob]      = useState<string>('all')
  const [sortMode,       setSortMode]       = useState<SortMode>('newest')
  const [statusFilter,   setStatusFilter]   = useState<StatusFilter>('all')
  const [expandSignal,   setExpandSignal]   = useState(0)
  const [collapseSignal, setCollapseSignal] = useState(0)

  const visible = cards.filter(c => !c.dismissed)

  // Apply status filter
  const statusFiltered = visible.filter(card => {
    if (statusFilter === 'all') return true
    if (statusFilter === 'analyzing') {
      return !card.analysis && card.steps.some(s => s.status === 'running')
    }
    if (statusFilter === 'fixable') {
      return card.analysis != null &&
        !DIAGNOSTIC_TYPES.has(card.analysis.fix_type) &&
        card.analysis.confidence >= CONFIDENCE_THRESHOLD &&
        !card.fixResult
    }
    if (statusFilter === 'manual') {
      return card.analysis != null && DIAGNOSTIC_TYPES.has(card.analysis.fix_type)
    }
    return true
  })

  // Build job map from status-filtered cards for the feed
  const jobMap = new Map<string, BuildCardType[]>()
  for (const card of statusFiltered) {
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

  // Sort groups
  const sortedGroups = [...allGroups].sort((a, b) => {
    if (sortMode === 'failures') {
      const aHasFail = a.cards.some(c => !c.successEvent)
      const bHasFail = b.cards.some(c => !c.successEvent)
      if (aHasFail && !bHasFail) return -1
      if (!aHasFail && bHasFail) return  1
    }
    return b.latest - a.latest
  })

  // Job list for tabs — always from all visible (not status-filtered)
  const jobs = Array.from(new Set(visible.map(c => c.job)))

  // Apply job tab filter on top of sorted groups
  const groups = activeJob === 'all' ? sortedGroups : sortedGroups.filter(g => g.job === activeJob)

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
        <QuickTriggers />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg">

      {/* Jenkins not configured banner */}
      {!isConfigured && (
        <div className="flex items-center gap-3 px-5 py-2.5 bg-warning/10 border-b border-warning/30 shrink-0">
          <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />
          <span className="text-[12px] font-mono text-warning flex-1">
            Jenkins not configured — build monitoring and fix execution are disabled.
          </span>
          <button
            onClick={onConfigure}
            className="text-[11px] font-mono font-semibold text-warning underline underline-offset-2 hover:opacity-80 transition-opacity cursor-pointer"
          >
            Configure →
          </button>
        </div>
      )}

      {/* Toolbar row 1 */}
      <div className="flex items-center justify-between px-5 py-2.5 border-b border-accent-border/40 shrink-0 bg-surface">
        <span className="text-[12px] font-mono text-text-muted">
          Last updated <span className="text-text-base font-semibold"><LiveTimestamp /></span>
        </span>
        <div className="flex items-center gap-1.5">
          {/* Sort toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSortMode(m => m === 'newest' ? 'failures' : 'newest')}
            className="gap-1.5 text-text-dim hover:text-text-base hover:bg-overlay/50 text-[12px] h-7 px-2.5 font-mono rounded-lg"
            title="Toggle sort order"
          >
            <ArrowDownUp className="h-3 w-3" strokeWidth={1.5} />
            {sortMode === 'newest' ? 'Newest first' : 'Failures first'}
          </Button>
          {/* Expand all */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpandSignal(n => n + 1)}
            className="gap-1.5 text-text-dim hover:text-text-base hover:bg-overlay/50 text-[12px] h-7 px-2.5 font-mono rounded-lg"
            title="Expand all cards"
          >
            <ChevronsUpDown className="h-3.5 w-3.5" strokeWidth={1.5} />
            Expand all
          </Button>
          {/* Collapse all */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapseSignal(n => n + 1)}
            className="gap-1.5 text-text-dim hover:text-text-base hover:bg-overlay/50 text-[12px] h-7 px-2.5 font-mono rounded-lg"
            title="Collapse all cards"
          >
            <ChevronsDownUp className="h-3.5 w-3.5" strokeWidth={1.5} />
            Collapse all
          </Button>
          {/* Clear all */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearAll}
            className="gap-2 text-text-dim hover:text-error hover:bg-overlay/50 text-[12px] h-7 px-2.5 font-mono rounded-lg"
          >
            <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
            Clear all
          </Button>
        </div>
      </div>

      {/* Toolbar row 2 — status filter chips */}
      <div className="flex items-center gap-1.5 px-4 py-2 border-b border-accent-border/40 shrink-0 bg-surface/90">
        {(['all', 'analyzing', 'fixable', 'manual'] as StatusFilter[]).map(f => (
          <button
            key={f}
            onClick={() => setStatusFilter(f)}
            className={cn(
              'px-3 py-1 rounded-lg text-[11px] font-mono border transition-all duration-150 shrink-0 cursor-pointer',
              statusFilter === f
                ? 'border-accent-border bg-white text-accent font-semibold shadow-sm'
                : 'border-accent-border/30 bg-white/40 text-text-muted hover:text-text-base hover:bg-white/70 hover:border-accent-border/60',
            )}
          >
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
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
          {groups.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
              <Activity className="h-8 w-8 text-text-dim" strokeWidth={1.5} />
              <p className="text-[13px] font-mono text-text-muted">No cards match the current filter</p>
            </div>
          )}
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
                        : <BuildCard
                            key={card.key}
                            card={card}
                            isLatestFailing={latestFailingKeys.has(card.key)}
                            onDismiss={onDismiss}
                            onOpenDetail={onOpenDetail}
                            onOpenDetailAtStage={onOpenDetailAtStage}
                            expandSignal={expandSignal}
                            collapseSignal={collapseSignal}
                          />
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

const TEST_JOBS = [
  { name: 'stage-fail-test',   label: 'Stage fail' },
  { name: 'tool-mismatch-test', label: 'Tool mismatch' },
  { name: 'pull-image-test',   label: 'Pull image' },
]

function QuickTriggers() {
  const [firing, setFiring] = useState<string | null>(null)
  async function trigger(name: string) {
    setFiring(name)
    try {
      await fetch('/api/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_name: name }),
      })
    } finally { setFiring(null) }
  }
  return (
    <div className="flex flex-col items-center gap-2.5">
      <p className="text-[10px] font-mono text-text-dim uppercase tracking-[0.14em]">Quick-trigger test jobs</p>
      <div className="flex gap-2">
        {TEST_JOBS.map(({ name, label }) => (
          <button
            key={name}
            onClick={() => trigger(name)}
            disabled={firing === name}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-accent-border/50 bg-white text-[11px] font-mono text-text-muted hover:text-accent hover:border-accent-border hover:bg-accent-dim transition-all duration-150 cursor-pointer disabled:opacity-50"
          >
            <Zap className="h-3 w-3 shrink-0" strokeWidth={2} />
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

function LiveTimestamp() {
  const [label, setLabel] = useState('just now')
  useEffect(() => {
    const start = Date.now()
    const id = setInterval(() => {
      const s = Math.floor((Date.now() - start) / 1000)
      if (s < 60) setLabel(`${s}s ago`)
      else if (s < 3600) setLabel(`${Math.floor(s / 60)}m ago`)
      else setLabel(`${Math.floor(s / 3600)}h ago`)
    }, 5000)
    return () => clearInterval(id)
  }, [])
  return <>{label}</>
}
