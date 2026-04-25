import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, ShieldAlert, Wrench, RefreshCw, Trash2, Clock,
  KeyRound, AlertTriangle, CheckCircle2, ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AnalysisCompleteEvent } from '@/types'

// ── fix type metadata ────────────────────────────────────────────────────────

const FIX_META: Record<string, {
  label: string
  icon: React.ReactNode
  accentClass: string
  barClass: string
  badgeClass: string
  agentNote: string
}> = {
  fix_step_typo: {
    label: 'Fix Invalid DSL Step',
    icon: <Wrench className="h-5 w-5" strokeWidth={1.8} />,
    accentClass: 'text-accent',
    barClass: 'from-accent via-accent/30 to-transparent',
    badgeClass: 'bg-accent-dim border-accent-border text-accent',
    agentNote: 'Agent will patch the Jenkinsfile in Jenkins job config and retrigger',
  },
  configure_credential: {
    label: 'Create Missing Credential',
    icon: <KeyRound className="h-5 w-5" strokeWidth={1.8} />,
    accentClass: 'text-[#2e6da0]',
    barClass: 'from-[#2e6da0] via-[#2e6da0]/30 to-transparent',
    badgeClass: 'bg-info-dim border-[rgba(46,109,160,0.22)] text-[#2e6da0]',
    agentNote: 'Agent will POST to Jenkins system credential store',
  },
  configure_tool: {
    label: 'Patch Tool Name Mismatch',
    icon: <Wrench className="h-5 w-5" strokeWidth={1.8} />,
    accentClass: 'text-accent',
    barClass: 'from-accent via-accent/30 to-transparent',
    badgeClass: 'bg-accent-dim border-accent-border text-accent',
    agentNote: 'Agent will rewrite Jenkinsfile tool block and reconfigure the job',
  },
  pull_image: {
    label: 'Fix Bad Docker Image Tag',
    icon: <RefreshCw className="h-5 w-5" strokeWidth={1.8} />,
    accentClass: 'text-[#7b5ea7]',
    barClass: 'from-[#7b5ea7] via-[#7b5ea7]/30 to-transparent',
    badgeClass: 'bg-running-dim border-running-border text-running',
    agentNote: 'Agent will patch Dockerfile tag → latest and retrigger',
  },
  clear_cache: {
    label: 'Clear Build Cache',
    icon: <Trash2 className="h-5 w-5" strokeWidth={1.8} />,
    accentClass: 'text-warning',
    barClass: 'from-warning via-warning/30 to-transparent',
    badgeClass: 'bg-warning-dim border-[rgba(176,125,42,0.22)] text-warning',
    agentNote: 'Agent will trigger build with cache-bust parameter',
  },
  retry: {
    label: 'Retry Pipeline',
    icon: <RefreshCw className="h-5 w-5" strokeWidth={1.8} />,
    accentClass: 'text-success',
    barClass: 'from-success via-success/30 to-transparent',
    badgeClass: 'bg-success-dim border-success-border text-success',
    agentNote: 'Agent will re-queue the job in Jenkins',
  },
  increase_timeout: {
    label: 'Increase Job Timeout',
    icon: <Clock className="h-5 w-5" strokeWidth={1.8} />,
    accentClass: 'text-[#b07d2a]',
    barClass: 'from-warning via-warning/30 to-transparent',
    badgeClass: 'bg-warning-dim border-[rgba(176,125,42,0.22)] text-warning',
    agentNote: 'Agent will double the timeout in job config XML',
  },
}

const DEFAULT_META = {
  label: 'Apply Fix',
  icon: <ShieldAlert className="h-5 w-5" strokeWidth={1.8} />,
  accentClass: 'text-accent',
  barClass: 'from-accent via-accent/30 to-transparent',
  badgeClass: 'bg-accent-dim border-accent-border text-accent',
  agentNote: 'Agent will apply the automated fix',
}

// ── component ────────────────────────────────────────────────────────────────

interface Props {
  open: boolean
  analysis: AnalysisCompleteEvent
  jobName: string
  buildNumber: string | number
  onAccept: () => void
  onCancel: () => void
}

export function ApplyFixModal({ open, analysis, jobName, buildNumber, onAccept, onCancel }: Props) {
  const meta = FIX_META[analysis.fix_type] ?? DEFAULT_META
  const overlayRef = useRef<HTMLDivElement>(null)

  // close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onCancel])

  // trap focus inside modal
  useEffect(() => {
    if (open) overlayRef.current?.focus()
  }, [open])

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-40 bg-[#1c1410]/40 backdrop-blur-[6px]"
            onClick={onCancel}
          />

          {/* Modal */}
          <motion.div
            key="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            ref={overlayRef}
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ type: 'spring', stiffness: 480, damping: 36 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
          >
            <div
              className="pointer-events-auto w-full max-w-[520px] rounded-2xl bg-white shadow-modal border border-[rgba(180,100,80,0.12)] overflow-hidden flex flex-col"
              onClick={e => e.stopPropagation()}
            >
              {/* Accent bar */}
              <div className={cn('h-[3px] w-full bg-gradient-to-r flex-shrink-0', meta.barClass)} />

              {/* Header */}
              <div className="flex items-start gap-3.5 px-5 pt-5 pb-4 border-b border-[rgba(180,100,80,0.1)]">
                <div className={cn(
                  'shrink-0 w-10 h-10 rounded-xl flex items-center justify-center',
                  'bg-[rgba(180,100,80,0.06)] border border-[rgba(180,100,80,0.1)]',
                  meta.accentClass,
                )}>
                  {meta.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <h2 id="modal-title" className="text-[15px] font-semibold text-text-primary leading-tight">
                    {meta.label}
                  </h2>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="font-mono text-[12px] text-text-muted bg-overlay/70 border border-[rgba(180,100,80,0.1)] rounded-md px-2 py-0.5">
                      {jobName}
                    </span>
                    <span className="font-mono text-[11px] text-text-dim">#{buildNumber}</span>
                    <span className={cn(
                      'text-[10px] font-mono font-semibold uppercase tracking-[0.1em] rounded-md px-2 py-0.5 border',
                      meta.badgeClass,
                    )}>
                      {analysis.fix_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>
                <button
                  onClick={onCancel}
                  className="shrink-0 text-text-dim hover:text-text-muted transition-colors rounded-lg p-1 hover:bg-overlay/60"
                  aria-label="Cancel"
                >
                  <X className="h-4 w-4" strokeWidth={1.5} />
                </button>
              </div>

              {/* Body */}
              <div className="px-5 py-4 space-y-4 overflow-y-auto max-h-[60vh]">

                {/* Root cause summary */}
                <div className="rounded-xl border border-[rgba(180,100,80,0.1)] bg-[#fffcfa] px-4 py-3.5">
                  <p className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.12em] mb-1.5">
                    Why this failed
                  </p>
                  <p className="text-[13px] text-text-base leading-relaxed">
                    {analysis.root_cause}
                  </p>
                </div>

                {/* What will happen — steps */}
                <div>
                  <p className="text-[10px] font-mono font-semibold text-text-muted uppercase tracking-[0.12em] mb-2.5">
                    What the agent will do
                  </p>
                  <ol className="space-y-2">
                    {analysis.steps.map((step, i) => (
                      <motion.li
                        key={i}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.06 + i * 0.04, duration: 0.18 }}
                        className="flex items-start gap-3"
                      >
                        <span className={cn(
                          'shrink-0 mt-0.5 flex items-center justify-center',
                          'w-[20px] h-[20px] rounded-full text-[10px] font-mono font-bold',
                          'border',
                          i === 0
                            ? cn('text-white border-transparent', getStepZeroBg(analysis.fix_type))
                            : 'bg-overlay/60 border-[rgba(180,100,80,0.14)] text-text-muted',
                        )}>
                          {i === 0 ? <ChevronRight className="h-3 w-3" strokeWidth={2.5} /> : i + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className={cn(
                            'text-[13px] leading-relaxed',
                            i === 0 ? 'text-text-primary font-medium' : 'text-text-base',
                          )}>
                            {step}
                          </p>
                          {i === 0 && (
                            <p className="text-[11px] font-mono text-text-dim mt-0.5">
                              {meta.agentNote}
                            </p>
                          )}
                        </div>
                      </motion.li>
                    ))}
                  </ol>
                </div>

                {/* Confidence + fix_suggestion */}
                <div className="flex items-center justify-between gap-3 pt-1">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0" strokeWidth={2} />
                    <span className="text-[12px] font-mono text-text-muted">
                      {Math.round(analysis.confidence * 100)}% confidence
                    </span>
                  </div>
                  <p className="text-[12px] text-text-dim italic text-right leading-relaxed max-w-[280px]">
                    "{analysis.fix_suggestion}"
                  </p>
                </div>

                {/* Warning note */}
                <div className="flex items-start gap-2.5 rounded-xl border border-[rgba(176,125,42,0.2)] bg-warning-dim px-3.5 py-3">
                  <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" strokeWidth={2} />
                  <p className="text-[12px] text-warning leading-relaxed">
                    This action will modify Jenkins configuration and retrigger the job.
                    It cannot be automatically undone.
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between gap-3 px-5 py-4 border-t border-[rgba(180,100,80,0.1)] bg-[#fffcfa]">
                <button
                  onClick={onCancel}
                  className={cn(
                    'h-9 px-5 rounded-xl text-[13px] font-semibold font-sans',
                    'border border-[rgba(180,100,80,0.18)] text-text-muted bg-white',
                    'hover:bg-overlay/60 hover:text-text-base hover:border-[rgba(180,100,80,0.28)]',
                    'transition-all duration-150 cursor-pointer',
                  )}
                >
                  Cancel
                </button>

                <button
                  onClick={onAccept}
                  className={cn(
                    'h-9 px-6 rounded-xl text-[13px] font-bold font-sans',
                    'flex items-center gap-2',
                    'text-white shadow-sm',
                    'transition-all duration-150 cursor-pointer active:scale-[0.98]',
                    getAcceptBtnClass(analysis.fix_type),
                  )}
                >
                  {meta.icon}
                  Accept & Apply Fix
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ── helpers ──────────────────────────────────────────────────────────────────

function getStepZeroBg(fixType: string) {
  const map: Record<string, string> = {
    configure_credential: 'bg-[#2e6da0]',
    configure_tool:       'bg-accent',
    fix_step_typo:        'bg-accent',
    pull_image:           'bg-[#7b5ea7]',
    clear_cache:          'bg-warning',
    retry:                'bg-success',
    increase_timeout:     'bg-warning',
  }
  return map[fixType] ?? 'bg-accent'
}

function getAcceptBtnClass(fixType: string) {
  const map: Record<string, string> = {
    configure_credential: 'bg-[#2e6da0] hover:bg-[#265d8c]',
    configure_tool:       'bg-accent hover:bg-accent-hi',
    fix_step_typo:        'bg-accent hover:bg-accent-hi',
    pull_image:           'bg-[#7b5ea7] hover:bg-[#6a4e94]',
    clear_cache:          'bg-warning hover:bg-[#9a6c22]',
    retry:                'bg-success hover:bg-[#246b50]',
    increase_timeout:     'bg-warning hover:bg-[#9a6c22]',
  }
  return map[fixType] ?? 'bg-accent hover:bg-accent-hi'
}
