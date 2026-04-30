import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ChevronDown, ChevronRight, X, Loader2, Wrench, AlertTriangle, Hash, CheckCircle2, Clock, Copy, Check, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AgentStepRow, PipelineStageRow } from './StageGraph'
import { ApplyFixModal } from './ApplyFixModal'
import { cn } from '@/lib/utils'
import type { BuildCard as BuildCardType, CredentialFields } from '@/types'

const CONFIDENCE_THRESHOLD = 0.75

function fmtTime(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000)
  if (s < 60)   return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function SuccessBuildCard({ card, onDiscard }: { card: BuildCardType; onDiscard: () => void }) {
  const { successEvent } = card
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
      className="relative rounded-xl border border-success-border overflow-hidden bg-white shadow-card"
    >
      <div className="h-[2px] w-full bg-gradient-to-r from-success via-success/30 to-transparent" />
      <div className="flex items-center gap-3 px-4 py-3.5">
        <CheckCircle2 className="h-[18px] w-[18px] text-success shrink-0" strokeWidth={2} />
        <span className="text-[14px] font-semibold text-text-primary font-mono truncate flex-1">{card.job}</span>
        <div className="flex items-center gap-2 shrink-0">
          <span className="flex items-center gap-1.5 text-[11px] font-mono text-text-muted bg-overlay/60 border border-accent-border/40 rounded-lg px-2 py-1">
            <Hash className="h-3 w-3" />{card.build}
          </span>
          <span className="text-[11px] font-mono text-success bg-success-dim border border-success-border rounded-lg px-2 py-1">
            passed
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onDiscard}
          className="ml-1 text-[12px] h-7 px-3 font-mono text-text-muted hover:text-text-primary border border-accent-border/40 rounded-lg"
        >
          Discard
        </Button>
      </div>
      {successEvent?.previous_root_cause && (
        <div className="px-4 pb-4">
          <div className="rounded-xl border border-success-border bg-success-dim px-3.5 py-3 space-y-1.5">
            <p className="text-[10px] font-mono font-semibold text-success uppercase tracking-[0.12em]">
              Previous failure resolved
              {successEvent.previous_failed_build && (
                <span className="ml-1.5 text-text-muted normal-case font-normal">
                  (build #{successEvent.previous_failed_build})
                </span>
              )}
            </p>
            <p className="text-[13px] text-text-base leading-relaxed">{successEvent.previous_root_cause}</p>
          </div>
        </div>
      )}
    </motion.div>
  )
}

const DIAGNOSTIC_TYPES = new Set([
  'diagnostic_only', 'missing_plugin',
])

export function BuildCard({ card, isLatestFailing, onDismiss, onOpenDetail, onOpenDetailAtStage, expandSignal, collapseSignal }: {
  card: BuildCardType
  isLatestFailing?: boolean
  onDismiss: (k: string) => void
  onOpenDetail: (card: BuildCardType) => void
  onOpenDetailAtStage?: (card: BuildCardType, stage: string) => void
  expandSignal?: number
  collapseSignal?: number
}) {
  const [expanded,      setExpanded]      = useState(true)
  const [agentExpanded, setAgentExpanded] = useState(!card.analysis)

  useEffect(() => { if (expandSignal)   setExpanded(true)  }, [expandSignal])
  useEffect(() => { if (collapseSignal) setExpanded(false) }, [collapseSignal])
  const [fixing,        setFixing]        = useState(false)
  const [modalOpen,     setModalOpen]     = useState(false)
  const [copied,        setCopied]        = useState(false)
  const [pendingCredRetrigger, setPendingCredRetrigger] = useState<{
    credentialId: string
    jenkinsUrl: string
  } | null>(null)

  const { analysis, fixResult, steps, dismissed } = card
  const isRunning  = !analysis && steps.some(s => s.status === 'running')
  const hasFailed  = steps.some(s => s.status === 'failed')
  const canAutoFix = analysis && !DIAGNOSTIC_TYPES.has(analysis.fix_type) &&
                     analysis.confidence >= CONFIDENCE_THRESHOLD && !fixResult && isLatestFailing

  async function applyFix(credFields?: CredentialFields | null) {
    if (!analysis) return
    setModalOpen(false)
    setFixing(true)

    const isSelfConfigure = analysis.fix_type === 'configure_credential' && credFields === null

    try {
      const body: Record<string, string | undefined> = {
        fix_type:     analysis.fix_type,
        job_name:     card.job,
        build_number: String(card.build),
      }

      if (analysis.fix_type === 'configure_tool' && analysis.verification?.mismatched_tools?.[0]) {
        const m = analysis.verification.mismatched_tools[0]
        body.referenced_name = m.referenced
        body.configured_name = m.configured
      }

      if (analysis.fix_type === 'configure_credential' && analysis.verification?.missing_credentials?.[0]) {
        body.credential_id    = analysis.verification.missing_credentials[0]
        body.credential_type  = credFields?.credential_type ?? analysis.credential_type
        if (credFields != null) {
          body.secret_value = credFields.secret_value
          body.username     = credFields.username
          body.password     = credFields.password
          body.ssh_username = credFields.ssh_username
          body.private_key  = credFields.private_key
        }
        if (isSelfConfigure) {
          body.skip_retrigger = 'true'
        }
      }

      if (analysis.fix_type === 'fix_step_typo' || analysis.fix_type === 'increase_timeout') {
        if (analysis.bad_step)     body.bad_step     = analysis.bad_step
        if (analysis.correct_step) body.correct_step = analysis.correct_step
      }

      if (analysis.fix_type === 'pull_image') {
        if (analysis.bad_image)     body.bad_image     = analysis.bad_image
        if (analysis.correct_image) body.correct_image = analysis.correct_image
      }

      await fetch('/api/fix', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      })

      if (isSelfConfigure && analysis.verification?.missing_credentials?.[0]) {
        const settings = await fetch('/api/settings').then(r => r.json()).catch(() => ({}))
        setPendingCredRetrigger({
          credentialId: analysis.verification.missing_credentials[0],
          jenkinsUrl:   settings.jenkins_url ?? '',
        })
      }
    } finally { setFixing(false) }
  }

  const borderColor = hasFailed  ? 'border-error-border'
    : isRunning ? 'border-running-border'
    : analysis  ? 'border-success-border'
    : 'border-accent-border/40'

  const accentBar = hasFailed  ? 'from-error via-error/25 to-transparent'
    : isRunning ? 'from-running via-running/25 to-transparent'
    : analysis  ? 'from-success via-success/25 to-transparent'
    : 'from-accent-border/60 to-transparent'

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: dismissed ? 0.4 : 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
      className={cn(
        'relative rounded-xl border overflow-hidden transition-opacity duration-300 bg-white shadow-card',
        borderColor,
      )}
    >
      <div className={cn('w-full bg-gradient-to-r', accentBar, hasFailed ? 'h-[3px]' : 'h-[2px]')} />

      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3.5 cursor-pointer select-none hover:bg-overlay/20 transition-colors duration-150"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-text-dim hover:text-text-muted transition-colors">
          {expanded
            ? <ChevronDown  className="h-4 w-4" strokeWidth={1.5} />
            : <ChevronRight className="h-4 w-4" strokeWidth={1.5} />}
        </span>
        <span
          className="text-[14px] font-semibold text-text-primary font-mono truncate flex-1 cursor-pointer hover:text-accent transition-colors"
          onClick={e => { e.stopPropagation(); onOpenDetail(card) }}
          title="View logs and tool crawler"
        >
          {card.job}
        </span>
        <div className="flex items-center gap-2 shrink-0">
          {isRunning && <Badge variant="accent"><Loader2 className="h-3 w-3 animate-spin" />analyzing</Badge>}
          {analysis && !isRunning && (
            <div className="flex items-center gap-1.5 shrink-0">
              <div className="w-16 h-1.5 rounded-full bg-accent-border/30 overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all duration-500', analysis.confidence >= CONFIDENCE_THRESHOLD ? 'bg-success' : 'bg-warning')}
                  style={{ width: `${Math.round(analysis.confidence * 100)}%` }}
                />
              </div>
              <span className={cn('text-[11px] font-mono', analysis.confidence >= CONFIDENCE_THRESHOLD ? 'text-success' : 'text-warning')}>
                {Math.round(analysis.confidence * 100)}%
              </span>
            </div>
          )}
          {fixResult && <Badge variant={fixResult.success ? 'success' : 'error'}>{fixResult.success ? 'fixed' : 'failed'}</Badge>}
        </div>
        <span className="flex items-center gap-1 text-[10px] font-mono text-text-dim shrink-0">
          <Clock className="h-3 w-3" strokeWidth={1.5} />
          {fmtTime(card.createdAt)}
        </span>
        <button
          onClick={e => { e.stopPropagation(); onDismiss(card.key) }}
          className="ml-1 p-1 rounded-lg text-text-dim hover:text-text-primary hover:bg-overlay/50 transition-colors cursor-pointer"
        >
          <X className="h-4 w-4" strokeWidth={1.5} />
        </button>
      </div>

      {/* Body */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3.5">
          {analysis?.pipeline_stages && analysis.pipeline_stages.length > 0 && (
            <div>
              <SectionLabel>Pipeline Stages</SectionLabel>
              <PipelineStageRow
                stages={analysis.pipeline_stages}
                onStageClick={onOpenDetailAtStage ? s => onOpenDetailAtStage(card, s.name) : undefined}
              />
            </div>
          )}

          <div>
            <button
              onClick={() => setAgentExpanded(v => !v)}
              className="flex items-center gap-2 cursor-pointer mb-2 group"
            >
              {agentExpanded
                ? <ChevronDown  className="h-3.5 w-3.5 text-text-dim group-hover:text-text-muted transition-colors" strokeWidth={2} />
                : <ChevronRight className="h-3.5 w-3.5 text-text-dim group-hover:text-text-muted transition-colors" strokeWidth={2} />}
              <span className="text-[10px] font-mono font-semibold text-text-muted uppercase tracking-[0.12em] group-hover:text-text-base transition-colors">
                Agent Steps
              </span>
            </button>
            {agentExpanded && <AgentStepRow stages={steps} />}
          </div>

          {analysis && (
            <div className="rounded-xl border border-accent-border/40 bg-overlay/30 p-4 space-y-3.5">
              <div className="flex items-center justify-between">
                <SectionLabel>Root Cause</SectionLabel>
                <span className="flex items-center gap-1 text-[11px] font-mono text-text-dim mb-2">
                  <Hash className="h-3 w-3" />{card.build}
                </span>
              </div>
              <p className="text-[13px] leading-relaxed text-text-primary font-medium -mt-1">{analysis.root_cause}</p>
              {analysis.steps && analysis.steps.length > 0 ? (
                <div>
                  <SectionLabel>Fix Steps</SectionLabel>
                  <ol className="space-y-1.5 mt-1">
                    {analysis.steps.map((step, i) => (
                      <li key={i} className="flex items-start gap-2.5 text-[13px] text-text-base leading-relaxed">
                        <span className="shrink-0 mt-0.5 flex items-center justify-center w-[18px] h-[18px] rounded-full bg-accent/10 border border-accent/20 text-[10px] font-mono font-semibold text-accent">
                          {i + 1}
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : analysis.fix_suggestion ? (
                <InfoBlock label="Suggestion" text={analysis.fix_suggestion} />
              ) : null}
              {analysis.log_excerpt && (
                <div>
                  <SectionLabel>Log Excerpt</SectionLabel>
                  <button
                    onClick={() => onOpenDetail(card)}
                    className="mt-1.5 w-full text-left rounded-xl border border-accent-border/40 bg-overlay/40 hover:border-accent-border/70 hover:bg-overlay/60 transition-colors cursor-pointer overflow-hidden group"
                  >
                    <div className="flex">
                      <div className="w-[3px] shrink-0 bg-error/50 rounded-l-xl" />
                      <div className="px-3.5 py-3 flex-1 min-w-0">
                        <pre className="text-[12px] font-mono text-text-base leading-relaxed whitespace-pre-wrap overflow-hidden line-clamp-3 pointer-events-none">
                          {analysis.log_excerpt}
                        </pre>
                        <p className="mt-2 text-[11px] font-mono text-accent group-hover:text-accent/80 transition-colors">
                          View full logs →
                        </p>
                      </div>
                    </div>
                  </button>
                </div>
              )}
            </div>
          )}

          {analysis && !fixResult && isLatestFailing && (
            <div className="flex items-center gap-2.5">
              {canAutoFix ? (
                <Button
                  size="sm"
                  onClick={() => setModalOpen(true)}
                  disabled={fixing}
                  className="gap-2 bg-success hover:bg-success/90 text-white font-semibold border-0 text-[13px] h-9 px-4 font-mono rounded-lg shadow-soft"
                >
                  {fixing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wrench className="h-3.5 w-3.5" strokeWidth={2} />}
                  {fixing ? 'Applying…' : 'Apply Fix'}
                </Button>
              ) : (
                <div className="flex items-center gap-2 text-[12px] text-warning font-mono">
                  <AlertTriangle className="h-4 w-4" strokeWidth={2} />
                  {DIAGNOSTIC_TYPES.has(analysis.fix_type) ? 'Requires manual action' : 'Low confidence — review recommended'}
                </div>
              )}
              {DIAGNOSTIC_TYPES.has(analysis.fix_type) && analysis.steps && analysis.steps.length > 0 && (
                <button
                  onClick={() => {
                    const text = analysis.steps!.map((s, i) => `${i + 1}. ${s}`).join('\n')
                    navigator.clipboard.writeText(text).then(() => {
                      setCopied(true)
                      setTimeout(() => setCopied(false), 2000)
                    })
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-accent-border/50 text-[11px] font-mono text-text-muted hover:text-text-primary hover:bg-overlay/50 transition-colors cursor-pointer"
                >
                  {copied ? <Check className="h-3 w-3 text-success" strokeWidth={2} /> : <Copy className="h-3 w-3" strokeWidth={1.5} />}
                  {copied ? 'Copied!' : 'Copy steps'}
                </button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDismiss(card.key)}
                className="ml-auto text-text-dim hover:text-text-muted text-[12px] h-9 font-mono rounded-lg hover:bg-overlay/50"
              >
                Dismiss
              </Button>
            </div>
          )}

          {analysis && modalOpen && (
            <ApplyFixModal
              open={modalOpen}
              analysis={analysis}
              jobName={card.job}
              buildNumber={card.build}
              onAccept={applyFix}
              onCancel={() => setModalOpen(false)}
            />
          )}

                {/* Pending credential retrigger banner */}
                {pendingCredRetrigger && (
                  <div className="mt-2 rounded-xl border border-[rgba(46,109,160,0.25)] bg-[#f0f7ff] px-4 py-3 flex items-start gap-3">
                    <KeyRound className="h-4 w-4 text-[#2e6da0] shrink-0 mt-0.5" strokeWidth={1.8} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] text-[#1e4a72] font-medium leading-relaxed">
                        Credential <code className="font-mono bg-[#dbeafe] px-1 rounded">{pendingCredRetrigger.credentialId}</code> created as placeholder.
                      </p>
                      <p className="text-[11px] text-[#2e6da0] mt-0.5">Fill the value in Jenkins, then retrigger.</p>
                      <div className="flex gap-2 mt-2">
                        {pendingCredRetrigger.jenkinsUrl && (
                          <a
                            href={`${pendingCredRetrigger.jenkinsUrl}/credentials/store/system/domain/_/credential/${pendingCredRetrigger.credentialId}/update`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="h-7 px-3 rounded-lg text-[11px] font-semibold border border-[rgba(46,109,160,0.3)] text-[#2e6da0] bg-white hover:bg-[#dbeafe] transition-colors inline-flex items-center gap-1"
                          >
                            Open Jenkins ↗
                          </a>
                        )}
                        <button
                          onClick={async () => {
                            setPendingCredRetrigger(null)
                            await fetch('/api/fix', {
                              method:  'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body:    JSON.stringify({
                                fix_type:     'retry',
                                job_name:     card.job,
                                build_number: String(card.build),
                              }),
                            })
                          }}
                          className="h-7 px-3 rounded-lg text-[11px] font-semibold bg-[#2e6da0] text-white hover:bg-[#265d8c] transition-colors cursor-pointer"
                        >
                          Retrigger Job
                        </button>
                      </div>
                    </div>
                    <button
                      onClick={() => setPendingCredRetrigger(null)}
                      className="shrink-0 text-text-dim hover:text-text-muted transition-colors"
                      aria-label="Dismiss"
                    >
                      <X className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                )}

          {fixResult && (
            <div className={cn(
              'text-[12px] font-mono rounded-xl px-3.5 py-3 border leading-relaxed space-y-1',
              fixResult.success
                ? 'bg-success-dim text-success border-success-border'
                : 'bg-error-dim text-error border-error-border'
            )}>
              <span>{fixResult.detail}</span>
              {fixResult.success && fixResult.next_build && (
                <span className="block text-[11px] opacity-80">
                  Build #{fixResult.next_build} queued
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-mono font-semibold text-text-muted uppercase tracking-[0.12em] mb-2">
      {children}
    </p>
  )
}

function InfoBlock({ label, text, highlight }: { label: string; text: string; highlight?: boolean }) {
  return (
    <div>
      <SectionLabel>{label}</SectionLabel>
      <p className={cn('text-[13px] leading-relaxed', highlight ? 'text-text-primary font-medium' : 'text-text-base')}>
        {text}
      </p>
    </div>
  )
}
