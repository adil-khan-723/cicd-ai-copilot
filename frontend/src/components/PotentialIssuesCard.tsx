import { useState } from 'react'
import { ShieldAlert, Lightbulb, ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PotentialIssue } from '@/types'

interface PotentialIssuesCardProps {
  issues: PotentialIssue[]
}

function isAutoFixable(p: PotentialIssue): boolean {
  if (p.fix_type === 'logic_error') return false
  if (p.fix_type === 'fix_step_typo' && !p.correct_line) return false
  return true
}

export function PotentialIssuesCard({ issues }: PotentialIssuesCardProps) {
  const [openSuggestions, setOpenSuggestions] = useState<Record<number, boolean>>({})

  if (!issues || issues.length === 0) return null

  return (
    <div className="rounded-xl border border-warning-border bg-warning-dim/40 overflow-hidden">
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-warning-border/40 bg-warning-dim/60">
        <ShieldAlert className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />
        <span className="text-[11px] font-mono font-semibold text-warning uppercase tracking-[0.12em]">
          Related Issues in This Stage ({issues.length})
        </span>
        <span className="ml-auto text-[10px] font-mono text-text-dim italic">
          Apply Fix above to resolve auto-fixable items
        </span>
      </div>

      <div className="px-4 py-3 space-y-2.5">
        {issues.map((issue, idx) => {
          const fixable = isAutoFixable(issue)
          const hasManualSteps = !fixable && (issue.manual_steps?.length ?? 0) > 0
          const open = openSuggestions[idx] ?? false
          return (
            <div
              key={idx}
              className="rounded-lg border border-warning-border/60 bg-white/60 px-3.5 py-3 space-y-2"
            >
              <div className="flex items-center gap-2">
                <span className={cn(
                  'text-[9px] font-mono font-semibold uppercase tracking-[0.12em] px-1.5 py-0.5 rounded-md border',
                  issue.confidence === 'confirmed'
                    ? 'text-warning bg-warning-dim border-warning-border'
                    : issue.confidence === 'unverified'
                    ? 'text-text-muted bg-overlay/40 border-accent-border/40'
                    : 'text-accent bg-accent/10 border-accent/30'
                )}>
                  {issue.confidence === 'confirmed' ? 'confirmed' : issue.confidence === 'unverified' ? 'unverified' : 'llm analysis'}
                </span>
                <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">{issue.type}</span>
                <span className={cn(
                  'ml-auto text-[9px] font-mono font-semibold uppercase tracking-[0.1em] px-1.5 py-0.5 rounded-md border',
                  fixable
                    ? 'text-success bg-success-dim border-success-border'
                    : 'text-text-muted bg-overlay/40 border-accent-border/40'
                )}>
                  {fixable ? 'auto-fixable' : 'manual'}
                </span>
              </div>

              <p className="text-[13px] text-text-primary leading-relaxed">{issue.issue}</p>

              <pre className="text-[11px] font-mono text-text-base bg-overlay/40 border border-accent-border/30 rounded-md px-2.5 py-1.5 overflow-x-auto whitespace-pre-wrap">
                {issue.line}
              </pre>

              {hasManualSteps && (
                <div className="pt-1">
                  <button
                    onClick={() => setOpenSuggestions(prev => ({ ...prev, [idx]: !open }))}
                    className="flex items-center gap-1.5 text-[11px] font-mono font-semibold text-warning hover:text-warning/80 transition-colors cursor-pointer"
                  >
                    {open
                      ? <ChevronDown className="h-3 w-3" strokeWidth={2} />
                      : <ChevronRight className="h-3 w-3" strokeWidth={2} />}
                    <Lightbulb className="h-3 w-3" strokeWidth={2} />
                    {open ? 'Hide Suggestion' : 'Show Suggestion'}
                  </button>
                  {open && (
                    <ol className="mt-2 ml-1 space-y-1.5">
                      {issue.manual_steps!.map((step, i) => (
                        <li key={i} className="flex items-start gap-2.5 text-[12px] text-text-base leading-relaxed">
                          <span className="shrink-0 mt-0.5 flex items-center justify-center w-[18px] h-[18px] rounded-full bg-warning-dim border border-warning-border text-[10px] font-mono font-semibold text-warning">
                            {i + 1}
                          </span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
