import { useState } from 'react'
import { AlertTriangle, ShieldAlert, Wrench, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { PotentialIssue } from '@/types'

interface PotentialIssuesCardProps {
  issues: PotentialIssue[]
  onFixIssue: (issue: PotentialIssue, idx: number) => Promise<{ ok: boolean; error?: string }>
}

export function PotentialIssuesCard({ issues, onFixIssue }: PotentialIssuesCardProps) {
  const [fixing, setFixing] = useState<Record<number, boolean>>({})
  const [fixed, setFixed] = useState<Record<number, boolean>>({})
  const [errors, setErrors] = useState<Record<number, string>>({})

  if (!issues || issues.length === 0) return null

  async function handleFix(issue: PotentialIssue, idx: number) {
    setFixing(f => ({ ...f, [idx]: true }))
    setErrors(e => { const n = { ...e }; delete n[idx]; return n })
    try {
      const res = await onFixIssue(issue, idx)
      if (res.ok) {
        setFixed(f => ({ ...f, [idx]: true }))
      } else {
        setErrors(e => ({ ...e, [idx]: res.error ?? 'Fix failed' }))
      }
    } finally {
      setFixing(f => ({ ...f, [idx]: false }))
    }
  }

  return (
    <div className="rounded-xl border border-warning-border bg-warning-dim/40 overflow-hidden">
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-warning-border/40 bg-warning-dim/60">
        <ShieldAlert className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />
        <span className="text-[11px] font-mono font-semibold text-warning uppercase tracking-[0.12em]">
          Related Issues in This Stage ({issues.length})
        </span>
      </div>

      <div className="px-4 py-3 space-y-2.5">
        {issues.map((issue, idx) => {
          const isLogicOnly = issue.fix_type === 'logic_error'
          const isUnverified = issue.confidence === 'unverified'
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
              </div>

              <p className="text-[13px] text-text-primary leading-relaxed">{issue.issue}</p>

              <pre className="text-[11px] font-mono text-text-base bg-overlay/40 border border-accent-border/30 rounded-md px-2.5 py-1.5 overflow-x-auto whitespace-pre-wrap">
                {issue.line}
              </pre>

              <div className="flex items-center gap-2 pt-1">
                {!fixed[idx] && !isLogicOnly && (
                  <Button
                    size="sm"
                    disabled={fixing[idx]}
                    onClick={() => handleFix(issue, idx)}
                    className="gap-1.5 bg-warning hover:bg-warning/90 text-white font-semibold border-0 text-[12px] h-8 px-3 font-mono rounded-lg shadow-soft"
                  >
                    {fixing[idx]
                      ? <><Loader2 className="h-3 w-3 animate-spin" />Fixing…</>
                      : <><Wrench className="h-3 w-3" strokeWidth={2} />Fix this</>}
                  </Button>
                )}
                {fixed[idx] && (
                  <span className="text-[12px] font-mono text-success font-semibold">✓ Fixed</span>
                )}
                {isLogicOnly && (
                  <span className="text-[11px] font-mono text-text-muted italic">Manual review required</span>
                )}
                {isUnverified && !isLogicOnly && !fixed[idx] && (
                  <span className="text-[10px] font-mono text-text-dim">Jenkins API unreachable — review before fixing</span>
                )}
                {errors[idx] && (
                  <span className="text-[11px] font-mono text-error flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" strokeWidth={2} />
                    {errors[idx]}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
