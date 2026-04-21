import { useState, useEffect, useRef, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  X, Copy, Check, ChevronDown, ChevronRight,
  Wrench, Puzzle, KeyRound, AlertTriangle, CheckCircle2,
  Loader2, ArrowDown, Terminal, Maximize2, Minimize2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BuildCard, VerificationData, VerificationToolMismatch } from '@/types'

interface BuildDetailDrawerProps {
  card: BuildCard | null
  onClose: () => void
}

type DrawerTab = 'logs' | 'crawler'

export function BuildDetailDrawer({ card, onClose }: BuildDetailDrawerProps) {
  const [tab,      setTab]      = useState<DrawerTab>('logs')
  const [expanded, setExpanded] = useState(false)

  // Reset to logs tab and collapse when a new card is selected
  useEffect(() => { if (card) { setTab('logs'); setExpanded(false) } }, [card?.key])

  // Close on Escape key
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <AnimatePresence>
      {card && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-black/20"
            onClick={onClose}
          />

          {/* Drawer panel */}
          <motion.div
            key="drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 400, damping: 38 }}
            className="fixed right-0 top-0 bottom-0 z-50 flex flex-col bg-surface border-l border-accent-border/60 shadow-2xl transition-[width] duration-200"
            style={{ width: expanded ? '100vw' : 'clamp(480px, 45vw, 720px)' }}
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-5 py-3.5 border-b border-accent-border/40 shrink-0 bg-white">
              <Terminal className="h-4 w-4 text-text-dim shrink-0" strokeWidth={1.5} />
              <span className="font-mono text-[14px] font-semibold text-text-primary truncate flex-1">
                {card.job}
              </span>
              <span className="flex items-center gap-1 text-[11px] font-mono text-text-muted bg-overlay/60 border border-accent-border/40 rounded-lg px-2 py-1 shrink-0">
                #{card.build}
              </span>
              {card.analysis?.failed_stage && (
                <span className="text-[11px] font-mono bg-error-dim text-error border border-error-border rounded-lg px-2 py-1 shrink-0 max-w-[160px] truncate">
                  failed: {card.analysis.failed_stage}
                </span>
              )}
              <button
                onClick={() => setExpanded(v => !v)}
                className="text-text-dim hover:text-text-primary transition-colors cursor-pointer shrink-0"
                aria-label={expanded ? 'Collapse drawer' : 'Expand drawer'}
                title={expanded ? 'Collapse' : 'Expand to full width'}
              >
                {expanded
                  ? <Minimize2 className="h-4 w-4" strokeWidth={1.5} />
                  : <Maximize2 className="h-4 w-4" strokeWidth={1.5} />}
              </button>
              <button
                onClick={onClose}
                className="ml-1 text-text-dim hover:text-text-primary transition-colors cursor-pointer shrink-0"
                aria-label="Close drawer"
              >
                <X className="h-4 w-4" strokeWidth={1.5} />
              </button>
            </div>

            {/* Tab bar */}
            <div className="flex items-center gap-1 px-4 py-2 border-b border-accent-border/40 shrink-0 bg-surface/80">
              {(['logs', 'crawler'] as DrawerTab[]).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    'px-3.5 py-1.5 rounded-lg text-[12px] font-mono border transition-all duration-150 cursor-pointer',
                    tab === t
                      ? 'border-accent-border bg-white text-accent font-semibold shadow-sm'
                      : 'border-accent-border/30 bg-white/40 text-text-muted hover:text-text-base hover:bg-white/70 hover:border-accent-border/60',
                  )}
                >
                  {t === 'logs' ? 'Logs' : 'Tool Crawler'}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-hidden">
              {tab === 'logs' && (
                <LogsTab
                  job={String(card.job)}
                  build={Number(card.build)}
                  failedStage={card.analysis?.failed_stage}
                />
              )}
              {tab === 'crawler' && (
                <CrawlerTab verification={card.analysis?.verification} />
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ─── Log noise filter ────────────────────────────────────────────────────────
// Strips Jenkins orchestration chatter — keeps only lines that carry signal.
const NOISE_PATTERNS = [
  /^\s*$/,                                          // blank lines
  /\[Pipeline\] Start of Pipeline/,
  /\[Pipeline\] End of Pipeline/,
  /\[Pipeline\] \/\/ stage/,                        // closing stage markers
  /\[Pipeline\] \}/,                                // closing brace
  /\[Pipeline\] node/,
  /\[Pipeline\] \{$/,                               // opening brace alone
  /Running on .+ in /,                              // "Running on agent in /path"
  /^Started by /,
  /^Triggering /,
  /Obtained .+ from /,                              // "Obtained Jenkinsfile from SCM"
  /^\s*\[Pipeline\] withEnv/,
  /^\s*\[Pipeline\] withCredentials/,
  /^\s*\[Pipeline\] parallel/,
  /^\s*\[Pipeline\] stage$/,
  /Checking out .+Revision/,
  /using credential/,
  /Fetching upstream changes/,
  /Merging remotes/,
  /FETCH_HEAD/,
  /Cleaning workspace/,
  / > git /,                                        // raw git commands
  /^\s*\[Pipeline\] script$/,
]

function filterLog(raw: string): string {
  return raw
    .split('\n')
    .filter(line => !NOISE_PATTERNS.some(p => p.test(line)))
    .join('\n')
}

// ─── Logs Tab ────────────────────────────────────────────────────────────────

interface LogsTabProps {
  job: string
  build: number
  failedStage?: string
}

function LogsTab({ job, build, failedStage }: LogsTabProps) {
  const [log, setLog]         = useState<string | null>(null)
  const [error, setError]     = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied]   = useState(false)
  const failedLineRef         = useRef<HTMLDivElement>(null)
  const scrollRef             = useRef<HTMLDivElement>(null)

  const fetchLog = useCallback(() => {
    setLoading(true)
    setError(null)
    fetch(`/api/build-log?job=${encodeURIComponent(job)}&build=${build}`)
      .then(async r => {
        if (!r.ok) {
          const data = await r.json().catch(() => ({}))
          throw new Error(data.detail ?? `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then(data => setLog(filterLog(data.log ?? '')))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [job, build])

  useEffect(() => { fetchLog() }, [fetchLog])

  function jumpToFailed() {
    failedLineRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  function copyLog() {
    if (!log) return
    navigator.clipboard.writeText(log).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-zinc-950 gap-3">
        <Loader2 className="h-6 w-6 text-zinc-400 animate-spin" strokeWidth={1.5} />
        <p className="text-[12px] font-mono text-zinc-500">Fetching log from Jenkins...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-zinc-950 gap-4">
        <AlertTriangle className="h-8 w-8 text-red-500" strokeWidth={1.5} />
        <p className="text-[13px] font-mono text-zinc-300">Failed to load log</p>
        <p className="text-[11px] font-mono text-zinc-500 max-w-xs text-center">{error}</p>
        <button
          onClick={fetchLog}
          className="mt-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-[12px] font-mono border border-zinc-700 transition-colors cursor-pointer"
        >
          Retry
        </button>
      </div>
    )
  }

  const lines = (log ?? '').split('\n')

  // Detect failed stage line range
  let failedStart = -1
  let failedEnd   = lines.length
  if (failedStage) {
    const startPattern = `[Pipeline] { (${failedStage})`
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].includes(startPattern)) { failedStart = i; break }
    }
    if (failedStart >= 0) {
      for (let i = failedStart + 1; i < lines.length; i++) {
        if (lines[i].includes('[Pipeline] }')) { failedEnd = i; break }
      }
    }
  }

  const inFailedRange = (i: number) => failedStart >= 0 && i >= failedStart && i <= failedEnd

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-800 shrink-0">
        {failedStage && failedStart >= 0 && (
          <button
            onClick={jumpToFailed}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-red-950/60 hover:bg-red-950/80 border border-red-900/60 text-red-400 text-[11px] font-mono transition-colors cursor-pointer"
          >
            <ArrowDown className="h-3 w-3" strokeWidth={2} />
            Jump to failed stage
          </button>
        )}
        {failedStage && (
          <span className="text-[11px] font-mono text-red-400 bg-red-950/40 border border-red-900/40 rounded-md px-2 py-1 truncate max-w-[200px]">
            {failedStage}
          </span>
        )}
        <div className="flex-1" />
        <button
          onClick={copyLog}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-[11px] font-mono transition-colors cursor-pointer"
        >
          {copied ? <Check className="h-3 w-3 text-green-400" strokeWidth={2} /> : <Copy className="h-3 w-3" strokeWidth={1.5} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      {/* Log lines */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="py-2">
          {lines.map((line, i) => {
            const isFirst = failedStart >= 0 && i === failedStart
            return (
              <div
                key={i}
                ref={isFirst ? failedLineRef : undefined}
                className={cn(
                  'flex items-start group',
                  inFailedRange(i)
                    ? 'bg-red-950/20 border-l-2 border-red-500/70'
                    : 'border-l-2 border-transparent',
                )}
              >
                <span className="select-none w-10 text-right pr-3 text-[11px] font-mono text-zinc-600 shrink-0 leading-[1.6] pt-px">
                  {i + 1}
                </span>
                <span className={cn(
                  'flex-1 text-[12px] font-mono leading-[1.6] whitespace-pre-wrap break-all pr-4',
                  inFailedRange(i) ? 'text-zinc-200' : 'text-zinc-400',
                )}>
                  {line || ' '}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Tool Crawler Tab ─────────────────────────────────────────────────────────

function CrawlerTab({ verification }: { verification?: VerificationData }) {
  if (!verification) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
        <AlertTriangle className="h-8 w-8 text-text-dim" strokeWidth={1.5} />
        <p className="text-[13px] font-semibold text-text-base">No verification data available</p>
        <p className="text-[12px] font-mono text-text-muted">This build was processed before tool crawling was enabled.</p>
      </div>
    )
  }

  const hasTools   = verification.matched_tools.length > 0 || verification.mismatched_tools.length > 0
  const hasPlugins = verification.missing_plugins.length > 0
  const hasCreds   = verification.missing_credentials.length > 0
  const hasErrors  = verification.errors.length > 0
  const allClean   = !hasTools && !hasPlugins && !hasCreds && !hasErrors

  if (allClean) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
        <CheckCircle2 className="h-10 w-10 text-success" strokeWidth={1.5} />
        <p className="text-[13px] font-semibold text-text-base">Nothing to verify</p>
        <p className="text-[12px] font-mono text-text-muted">No tools or credentials referenced in this Jenkinsfile.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {hasErrors && (
        <div className="mx-4 mt-4 flex items-start gap-2.5 px-3.5 py-3 rounded-xl bg-warning-dim border border-warning/40">
          <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" strokeWidth={2} />
          <p className="text-[12px] font-mono text-warning leading-relaxed">
            Tool crawler could not fully verify — Jenkins API returned errors. Results may be incomplete.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3 p-4">
        <CrawlerSection
          icon={<Wrench className="h-3.5 w-3.5" strokeWidth={2} />}
          label="Tools"
          issueCount={verification.mismatched_tools.length}
        >
          {!hasTools ? (
            <EmptyRow text="No tools declared in Jenkinsfile" />
          ) : (
            <>
              {verification.matched_tools.map(name => (
                <ToolRow key={name} status="ok" label={name} />
              ))}
              {verification.mismatched_tools.map((m, i) => (
                <MismatchRow key={i} mismatch={m} />
              ))}
            </>
          )}
        </CrawlerSection>

        <CrawlerSection
          icon={<Puzzle className="h-3.5 w-3.5" strokeWidth={2} />}
          label="Plugins"
          issueCount={verification.missing_plugins.length}
        >
          {!hasPlugins ? (
            <ToolRow status="ok" label="All required plugins installed" />
          ) : (
            verification.missing_plugins.map(p => (
              <ToolRow key={p} status="missing" label={p} sublabel="not installed" />
            ))
          )}
        </CrawlerSection>

        <CrawlerSection
          icon={<KeyRound className="h-3.5 w-3.5" strokeWidth={2} />}
          label="Credentials"
          issueCount={verification.missing_credentials.length}
        >
          {!hasCreds ? (
            <ToolRow status="ok" label="All credentials found" />
          ) : (
            verification.missing_credentials.map(c => (
              <ToolRow key={c} status="missing" label={c} sublabel="not found in Jenkins" />
            ))
          )}
        </CrawlerSection>
      </div>
    </div>
  )
}

// ─── Crawler sub-components ───────────────────────────────────────────────────

function CrawlerSection({
  icon, label, issueCount, children,
}: {
  icon: React.ReactNode
  label: string
  issueCount: number
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  const hasIssues = issueCount > 0

  return (
    <div className="rounded-xl border border-accent-border/40 overflow-hidden bg-white">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2.5 w-full px-4 py-3 hover:bg-overlay/30 transition-colors cursor-pointer"
      >
        <span className={cn('text-text-dim', hasIssues && 'text-error')}>{icon}</span>
        <span className="text-[12px] font-mono font-semibold text-text-base flex-1 text-left">{label}</span>
        {hasIssues ? (
          <span className="text-[10px] font-mono bg-error-dim text-error border border-error-border rounded-full px-2 py-0.5">
            {issueCount} issue{issueCount !== 1 ? 's' : ''}
          </span>
        ) : (
          <span className="text-[10px] font-mono bg-success-dim text-success border border-success-border rounded-full px-2 py-0.5">
            ok
          </span>
        )}
        <span className="text-text-dim ml-1">
          {open
            ? <ChevronDown className="h-3.5 w-3.5" strokeWidth={2} />
            : <ChevronRight className="h-3.5 w-3.5" strokeWidth={2} />}
        </span>
      </button>
      {open && (
        <div className="border-t border-accent-border/30 divide-y divide-accent-border/20">
          {children}
        </div>
      )}
    </div>
  )
}

function ToolRow({ status, label, sublabel }: { status: 'ok' | 'missing'; label: string; sublabel?: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      {status === 'ok' ? (
        <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0" strokeWidth={2} />
      ) : (
        <AlertTriangle className="h-3.5 w-3.5 text-error shrink-0" strokeWidth={2} />
      )}
      <span className={cn('text-[12px] font-mono flex-1', status === 'ok' ? 'text-text-base' : 'text-error')}>
        {label}
      </span>
      {sublabel && (
        <span className="text-[11px] font-mono text-text-dim">{sublabel}</span>
      )}
    </div>
  )
}

function MismatchRow({ mismatch }: { mismatch: VerificationToolMismatch }) {
  const pct = Math.round(mismatch.match_score * 100)
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-[12px] font-mono">
          <span className="text-warning">&quot;{mismatch.referenced}&quot;</span>
          <span className="text-text-dim">→</span>
          <span className="text-text-base">&quot;{mismatch.configured}&quot;</span>
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          <div className="flex-1 h-1 rounded-full bg-accent-border/30 overflow-hidden">
            <div
              className="h-full rounded-full bg-warning"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-[10px] font-mono text-text-dim shrink-0">{pct}% match</span>
        </div>
      </div>
    </div>
  )
}

function EmptyRow({ text }: { text: string }) {
  return (
    <div className="px-4 py-2.5 text-[12px] font-mono text-text-dim">{text}</div>
  )
}
