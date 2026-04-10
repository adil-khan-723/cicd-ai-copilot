import { useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronDown, ChevronRight, X, Loader2, WrenchIcon, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StageGraph } from './StageGraph'
import { cn, timestamp } from '@/lib/utils'
import type { BuildCard as BuildCardType } from '@/types'

const CONFIDENCE_THRESHOLD = 0.75

const DIAGNOSTIC_TYPES = new Set([
  'diagnostic_only',
  'tool_mismatch',
  'missing_plugin',
  'missing_credential',
])

interface BuildCardProps {
  card: BuildCardType
  onDismiss: (key: string) => void
}

export function BuildCard({ card, onDismiss }: BuildCardProps) {
  const [expanded, setExpanded] = useState(true)
  const [fixing, setFixing] = useState(false)

  const { analysis, fixResult, steps, dismissed } = card
  // Still running only if we have no analysis yet AND a step is actively spinning
  const isRunning = !analysis && steps.some((s) => s.status === 'running')
  const hasFailed = steps.some((s) => s.status === 'failed')

  const canAutoFix =
    analysis &&
    !DIAGNOSTIC_TYPES.has(analysis.fix_type) &&
    analysis.confidence >= CONFIDENCE_THRESHOLD &&
    !fixResult

  async function applyFix() {
    if (!analysis) return
    setFixing(true)
    try {
      await fetch('/api/fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fix_type: analysis.fix_type,
          job_name: card.job,
          build_number: String(card.build),
        }),
      })
    } catch {
      // fix_result will arrive via SSE
    } finally {
      setFixing(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: dismissed ? 0.35 : 1, y: 0 }}
      className={cn(
        'rounded-lg border bg-card overflow-hidden transition-opacity',
        hasFailed ? 'border-error/20' :
        isRunning ? 'border-running/20' :
        'border-border'
      )}
    >
      {/* Card header */}
      <div
        className="flex items-center gap-2 px-3 py-2.5 cursor-pointer select-none hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <button className="text-text-dim hover:text-text-muted transition-colors">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </button>

        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-sm font-mono font-medium text-text-primary truncate">
            {card.job}
          </span>
          <Badge variant="muted" className="shrink-0">
            #{card.build}
          </Badge>
          {isRunning && (
            <Badge variant="running" className="shrink-0 gap-1">
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
              analyzing
            </Badge>
          )}
          {analysis && !isRunning && (
            <Badge
              variant={analysis.confidence >= CONFIDENCE_THRESHOLD ? 'success' : 'warning'}
              className="shrink-0"
            >
              {Math.round(analysis.confidence * 100)}% conf
            </Badge>
          )}
          {fixResult && (
            <Badge variant={fixResult.success ? 'success' : 'error'} className="shrink-0">
              {fixResult.success ? 'fixed' : 'fix failed'}
            </Badge>
          )}
        </div>

        <button
          className="text-text-dim hover:text-text-muted transition-colors ml-1"
          onClick={(e) => {
            e.stopPropagation()
            onDismiss(card.key)
          }}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3">
          {/* Stage graph */}
          <StageGraph stages={steps} />

          {/* Analysis */}
          {analysis && (
            <div className="rounded border border-border-subtle bg-surface/50 p-3 space-y-2">
              <div>
                <p className="text-[10px] font-mono text-text-dim uppercase tracking-wider mb-1">
                  Root Cause
                </p>
                <p className="text-xs text-text-primary leading-relaxed">{analysis.root_cause}</p>
              </div>

              {analysis.fix_suggestion && (
                <div>
                  <p className="text-[10px] font-mono text-text-dim uppercase tracking-wider mb-1">
                    Suggestion
                  </p>
                  <p className="text-xs text-text-muted leading-relaxed">
                    {analysis.fix_suggestion}
                  </p>
                </div>
              )}

              {analysis.log_excerpt && (
                <div>
                  <p className="text-[10px] font-mono text-text-dim uppercase tracking-wider mb-1">
                    Log Excerpt
                  </p>
                  <pre className="text-[10px] font-mono text-text-muted leading-relaxed whitespace-pre-wrap overflow-x-auto max-h-24 overflow-y-auto">
                    {analysis.log_excerpt}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Fix actions */}
          {analysis && !fixResult && (
            <div className="flex gap-2">
              {canAutoFix ? (
                <Button
                  size="sm"
                  variant="success"
                  onClick={applyFix}
                  disabled={fixing}
                  className="gap-1.5"
                >
                  {fixing ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <WrenchIcon className="h-3 w-3" />
                  )}
                  Apply Fix
                </Button>
              ) : (
                <div className="flex items-center gap-1.5 text-xs text-warning">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  <span>
                    {DIAGNOSTIC_TYPES.has(analysis.fix_type)
                      ? 'Requires manual action'
                      : 'Low confidence — manual review recommended'}
                  </span>
                </div>
              )}

              <Button
                size="sm"
                variant="ghost"
                onClick={() => onDismiss(card.key)}
                className="ml-auto"
              >
                Dismiss
              </Button>
            </div>
          )}

          {/* Fix result */}
          {fixResult && (
            <div
              className={cn(
                'text-xs rounded px-3 py-2 font-mono',
                fixResult.success
                  ? 'bg-success/5 text-success border border-success/10'
                  : 'bg-error/5 text-error border border-error/10'
              )}
            >
              {fixResult.detail}
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}
