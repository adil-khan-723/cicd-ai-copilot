import { AnimatePresence } from 'framer-motion'
import { Activity, Terminal } from 'lucide-react'
import { BuildCard } from './BuildCard'
import type { BuildCard as BuildCardType } from '@/types'

export function PipelineFeed({ cards, onDismiss }: { cards: BuildCardType[]; onDismiss: (k: string) => void }) {
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

  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto h-full">
      <AnimatePresence initial={false}>
        {[...cards].reverse().map(card => (
          <BuildCard key={card.key} card={card} onDismiss={onDismiss} />
        ))}
      </AnimatePresence>
    </div>
  )
}
