import { AnimatePresence } from 'framer-motion'
import { Activity } from 'lucide-react'
import { BuildCard } from './BuildCard'
import type { BuildCard as BuildCardType } from '@/types'

interface PipelineFeedProps {
  cards: BuildCardType[]
  onDismiss: (key: string) => void
}

export function PipelineFeed({ cards, onDismiss }: PipelineFeedProps) {
  if (cards.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-text-dim">
        <Activity className="h-8 w-8 opacity-20" />
        <div className="text-center">
          <p className="text-sm font-medium text-text-muted">Waiting for pipeline events</p>
          <p className="text-xs mt-1">
            Trigger a failure or send a webhook to see analysis here
          </p>
        </div>
        <div className="mt-2 text-xs font-mono text-text-dim bg-surface border border-border rounded px-3 py-2">
          POST /webhook/pipeline-failure
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto h-full">
      <AnimatePresence initial={false}>
        {[...cards].reverse().map((card) => (
          <BuildCard key={card.key} card={card} onDismiss={onDismiss} />
        ))}
      </AnimatePresence>
    </div>
  )
}
