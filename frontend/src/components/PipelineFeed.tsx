import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Terminal, Trash2, CheckCircle2, X } from 'lucide-react'
import { BuildCard, SuccessBuildCard } from './BuildCard'
import { Button } from '@/components/ui/button'
import type { BuildCard as BuildCardType } from '@/types'

interface PipelineFeedProps {
  cards:               BuildCardType[]
  onDismiss:           (k: string) => void
  onClearAll:          () => void
  onDiscardOldFailed:  (job: string) => void
}

export function PipelineFeed({ cards, onDismiss, onClearAll, onDiscardOldFailed }: PipelineFeedProps) {
  if (cards.length === 0) {
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

  // Jobs that have a success card AND still have old failed cards
  const jobsWithOldFailed = new Set(
    cards
      .filter(c => c.successEvent)
      .map(c => c.job)
      .filter(job => cards.some(c => c.job === job && !c.successEvent))
  )

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-glass shrink-0">
        <span className="text-xs font-mono text-text-muted">
          {cards.length} event{cards.length !== 1 ? 's' : ''}
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

      {/* Discard banners — one per job that passed with leftover failed cards */}
      <AnimatePresence>
        {[...jobsWithOldFailed].map(job => (
          <motion.div
            key={`discard-banner-${job}`}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 32 }}
            className="overflow-hidden shrink-0"
          >
            <div className="mx-4 mt-3 flex items-center gap-2.5 rounded-lg border border-success/20 bg-success-dim px-3.5 py-2.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0" strokeWidth={2} />
              <p className="text-xs text-text-muted flex-1">
                <span className="font-mono font-semibold text-success">{job}</span> passed —
                discard old failure cards?
              </p>
              <Button
                variant="success"
                size="sm"
                onClick={() => onDiscardOldFailed(job)}
                className="text-xs h-6 px-2.5"
              >
                Discard
              </Button>
              <button
                onClick={() => onDiscardOldFailed('')}
                className="text-text-dim hover:text-text-muted transition-colors cursor-pointer"
                title="Dismiss"
              >
                <X className="h-3.5 w-3.5" strokeWidth={1.5} />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Cards */}
      <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
        <AnimatePresence initial={false}>
          {[...cards].reverse().map(card =>
            card.successEvent
              ? <SuccessBuildCard key={card.key} card={card} onDismiss={onDismiss} />
              : <BuildCard key={card.key} card={card} onDismiss={onDismiss} />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
