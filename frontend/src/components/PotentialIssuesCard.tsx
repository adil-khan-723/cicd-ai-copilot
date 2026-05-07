import { useState } from 'react'
import { AlertTriangle, ShieldAlert, Wrench, Loader2, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { PotentialIssue, VerificationData } from '@/types'

interface PotentialIssuesCardProps {
  issues: PotentialIssue[]
  jobName: string
  buildNumber: string | number
  verification?: VerificationData
  isLatestFailing?: boolean
}

export function PotentialIssuesCard({
  issues,
  jobName,
  buildNumber,
  verification,
  isLatestFailing,
}: PotentialIssuesCardProps) {
  const [expanded, setExpanded] = useState(true)
  const [fixing, setFixing] = useState<Record<number, boolean>>({})
  const [fixed, setFixed] = useState<Record<number, boolean>>({})
  const [errors, setErrors] = useState<Record<number, string>>({})

  if (!issues || issues.length === 0) return null

  async function applyIssueFix(issue: PotentialIssue, idx: number) {
    setFixing(f => ({ ...f, [idx]: true }))
    setErrors(e => { const n = { ...e }; delete n[idx]; return n })

    const body: Record<string, string> = {
      fix_type: issue.fix_type === 'logic_error' ? 'diagnostic_only' : issue.fix_type,
      job_name: String(jobName),
      build_number: String(buildNumber),
    }

    if (issue.fix_type === 'configure_tool' && verification?.mismatched_tools?.length) {
      const match = verification.mismatched_tools.find(m => issue.line.includes(m.referenced))
      if (match) {
        body.referenced_name = match.referenced
        body.configured_name = match.configured
      }
    }

    if (issue.fix_type === 'configure_credential') {
      const m = issue.line.match(/credentials\s*\(\s*['"]([^'"]+)['"]|credentialsId\s*:\s*['"]([^'"]+)['"]/)
      if (m) body.credential_id = m[1] ?? m[2]
    }

    try {
      const res = await fetch('/api/fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        setFixed(f => ({ ...f, [idx]: true }))
      } else {
        const data = await res.json().catch(() => ({}))
        setErrors(e => ({ ...e, [idx]: data.detail ?? 'Fix failed' }))
      }
    } catch {
      setErrors(e => ({ ...e, [idx]: 'Network error' }))
    } finally {
      setFixing(f => ({ ...f, [idx]: false }))
    }
  }

  return (
    <div className="rounded-xl border border-warning-border bg-warning-dim/30 overflow-hidden">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-2.5 px-4 py-3 hover:bg-warning/5 transition-colors cursor-pointer"
      >
        {expanded
          ? <ChevronDown className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />
          : <ChevronRight className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />}
        <ShieldAlert className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />
        <span className="text-[11px] font-mono font-semibold text-warning uppercase tracking-[0.1em]">
          Also found in this stage ({issues.length} issue{issues.length !== 1 ? 's' : ''})
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-2.5">
          {issues.map((issue, idx) => (
            <div
              key={idx}
              className={cn(
                'rounded-lg border px-3.5 py-3 space-y-2',
                issue.confidence === 'confirmed'
                  ? 'border-warning-border bg-warning-dim/50'
                  : 'border-accent-border/40 bg-overlay/30'
              )}
            >
              <div className="flex items-center gap-2">
                <span className={cn(
                  'text-[9px] font-mono font-semibold uppercase tracking-[0.1em] px-1.5 py-0.5 rounded-md border',
                  issue.confidence === 'confirmed'
                    ? 'text-warning bg-warning-dim border-warning-border'
                    : issue.confidence === 'unverified'
                    ? 'text-text-muted bg-overlay/50 border-accent-border/40'
                    : 'text-text-dim bg-overlay/30 border-accent-border/20'
                )}>
                  {issue.confidence === 'confirmed' ? 'confirmed' : issue.confidence === 'unverified' ? 'unverified' : 'llm analysis'}
                </span>
                <span className="text-[10px] font-mono text-text-muted uppercase">{issue.type}</span>
              </div>

              <p className="text-[13px] text-text-primary leading-relaxed">{issue.issue}</p>

              <pre className="text-[11px] font-mono text-text-muted bg-overlay/50 border border-accent-border/30 rounded-lg px-2.5 py-1.5 overflow-x-auto whitespace-pre-wrap">
                {issue.line}
              </pre>

              {isLatestFailing && !fixed[idx] && issue.fix_type !== 'logic_error' && (
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={fixing[idx]}
                    onClick={() => applyIssueFix(issue, idx)}
                    className="h-7 px-3 text-[11px] font-mono border border-warning-border text-warning hover:bg-warning/10 gap-1.5"
                  >
                    {fixing[idx]
                      ? <><Loader2 className="h-3 w-3 animate-spin" />Fixing…</>
                      : <><Wrench className="h-3 w-3" strokeWidth={2} />Fix this</>}
                  </Button>
                  {errors[idx] && (
                    <span className="text-[11px] font-mono text-error flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" strokeWidth={2} />
                      {errors[idx]}
                    </span>
                  )}
                </div>
              )}
              {fixed[idx] && (
                <span className="text-[11px] font-mono text-success">✓ Fixed</span>
              )}
              {issue.fix_type === 'logic_error' && (
                <span className="text-[11px] font-mono text-text-muted italic">Requires manual review</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
