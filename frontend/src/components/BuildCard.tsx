import { useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronDown, ChevronRight, X, Loader2, Wrench, AlertTriangle, Hash } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StageGraph } from './StageGraph'
import { cn } from '@/lib/utils'
import type { BuildCard as BuildCardType } from '@/types'

const CONFIDENCE_THRESHOLD = 0.75

const DIAGNOSTIC_TYPES = new Set([
  'diagnostic_only', 'tool_mismatch', 'missing_plugin', 'missing_credential',
])

export function BuildCard({ card, onDismiss }: { card: BuildCardType; onDismiss: (k: string) => void }) {
  const [expanded, setExpanded] = useState(true)
  const [fixing,   setFixing]   = useState(false)

  const { analysis, fixResult, steps, dismissed } = card
  const isRunning  = !analysis && steps.some(s => s.status === 'running')
  const hasFailed  = steps.some(s => s.status === 'failed')
  const canAutoFix = analysis && !DIAGNOSTIC_TYPES.has(analysis.fix_type) &&
                     analysis.confidence >= CONFIDENCE_THRESHOLD && !fixResult

  async function applyFix() {
    if (!analysis) return
    setFixing(true)
    try {
      await fetch('/api/fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fix_type: analysis.fix_type, job_name: card.job, build_number: String(card.build) }),
      })
    } finally { setFixing(false) }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: dismissed ? 0.3 : 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
      className={cn(
        'relative rounded-xl border overflow-hidden transition-opacity duration-300',
        'bg-card shadow-card',
        hasFailed  ? 'border-error/20'   :
        isRunning  ? 'border-accent/20'  :
        analysis   ? 'border-success/15' : 'border-glass',
      )}
    >
      {/* Top accent line */}
      <div className={cn(
        'h-px w-full',
        hasFailed  ? 'bg-gradient-to-r from-error/60 via-error/20 to-transparent' :
        isRunning  ? 'bg-gradient-to-r from-accent/60 via-accent/20 to-transparent' :
        analysis   ? 'bg-gradient-to-r from-success/60 via-success/20 to-transparent' :
        'bg-gradient-to-r from-border-hi to-transparent'
      )} />

      {/* Card header */}
      <div
        className="flex items-center gap-2.5 px-4 py-3 cursor-pointer select-none hover:bg-white/[0.02] transition-colors duration-150"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-text-dim hover:text-text-muted transition-colors">
          {expanded
            ? <ChevronDown className="h-3.5 w-3.5" strokeWidth={1.5} />
            : <ChevronRight className="h-3.5 w-3.5" strokeWidth={1.5} />}
        </span>

        <span className="text-sm font-semibold text-text-primary font-mono truncate flex-1">
          {card.job}
        </span>

        <div className="flex items-center gap-1.5 shrink-0">
          <Badge variant="muted">
            <Hash className="h-2.5 w-2.5" />{card.build}
          </Badge>

          {isRunning && (
            <Badge variant="accent">
              <Loader2 className="h-2.5 w-2.5 animate-spin" />analyzing
            </Badge>
          )}

          {analysis && !isRunning && (
            <Badge variant={analysis.confidence >= CONFIDENCE_THRESHOLD ? 'success' : 'warning'}>
              {Math.round(analysis.confidence * 100)}% conf
            </Badge>
          )}

          {fixResult && (
            <Badge variant={fixResult.success ? 'success' : 'error'}>
              {fixResult.success ? 'fixed' : 'failed'}
            </Badge>
          )}
        </div>

        <button
          onClick={e => { e.stopPropagation(); onDismiss(card.key) }}
          className="ml-1 text-text-dim hover:text-text-muted transition-colors cursor-pointer"
        >
          <X className="h-3.5 w-3.5" strokeWidth={1.5} />
        </button>
      </div>

      {/* Body */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          <StageGraph stages={steps} />

          {analysis && (
            <div className="rounded-lg border border-glass bg-surface/60 p-3.5 space-y-3">
              <InfoBlock label="Root Cause" text={analysis.root_cause} highlight />
              {analysis.fix_suggestion && (
                <InfoBlock label="Suggestion" text={analysis.fix_suggestion} />
              )}
              {analysis.log_excerpt && (
                <div>
                  <Label>Log Excerpt</Label>
                  <pre className="mt-1 text-[11px] font-mono text-text-muted leading-relaxed whitespace-pre-wrap overflow-x-auto max-h-28 overflow-y-auto rounded border border-glass bg-bg/60 px-3 py-2">
                    {analysis.log_excerpt}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          {analysis && !fixResult && (
            <div className="flex items-center gap-2">
              {canAutoFix ? (
                <Button variant="success" size="sm" onClick={applyFix} disabled={fixing} className="gap-1.5">
                  {fixing
                    ? <Loader2 className="h-3 w-3 animate-spin" />
                    : <Wrench className="h-3 w-3" strokeWidth={2} />}
                  Apply Fix
                </Button>
              ) : (
                <div className="flex items-center gap-1.5 text-[11px] text-warning font-mono">
                  <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2} />
                  {DIAGNOSTIC_TYPES.has(analysis.fix_type)
                    ? 'Requires manual action'
                    : 'Low confidence — review recommended'}
                </div>
              )}
              <Button variant="ghost" size="sm" onClick={() => onDismiss(card.key)} className="ml-auto">
                Dismiss
              </Button>
            </div>
          )}

          {fixResult && (
            <div className={cn(
              'text-[11px] font-mono rounded-lg px-3 py-2.5 border',
              fixResult.success
                ? 'bg-success-dim text-success border-success/15'
                : 'bg-error-dim text-error border-error/15'
            )}>
              {fixResult.detail}
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-widest mb-1">
      {children}
    </p>
  )
}

function InfoBlock({ label, text, highlight }: { label: string; text: string; highlight?: boolean }) {
  return (
    <div>
      <Label>{label}</Label>
      <p className={cn('text-xs leading-relaxed', highlight ? 'text-text-primary' : 'text-text-muted')}>
        {text}
      </p>
    </div>
  )
}
