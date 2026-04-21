import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, Play, Loader2, CheckCircle2, XCircle, AlertCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { JenkinsJob } from '@/types'

interface JobsBrowserProps {
  onJenkinsStatus?: (s: 'connected' | 'disconnected' | 'unknown') => void
  wireStatus?:      Record<string, 'ok' | 'already' | 'err'>
  onWireStatus?:    (name: string, status: 'ok' | 'already' | 'err') => void
}

const STATUS_CONFIG: Record<string, {
  label: string
  labelClass: string
  icon: React.ReactNode
  leftBorder: string
}> = {
  success: {
    label:      'passed',
    labelClass: 'text-success bg-success-dim border-success-border',
    icon:       <CheckCircle2 className="h-[18px] w-[18px] text-success" strokeWidth={2} />,
    leftBorder: 'hover:border-l-success',
  },
  failure: {
    label:      'failed',
    labelClass: 'text-error bg-error-dim border-error-border',
    icon:       <XCircle className="h-[18px] w-[18px] text-error" strokeWidth={2} />,
    leftBorder: 'hover:border-l-error',
  },
  running: {
    label:      'running',
    labelClass: 'text-running bg-running-dim border-running-border',
    icon:       <Loader2 className="h-[18px] w-[18px] text-running animate-spin" strokeWidth={2} />,
    leftBorder: 'hover:border-l-running',
  },
  unknown: {
    label:      'unknown',
    labelClass: 'text-text-muted bg-overlay/60 border-accent-border/40',
    icon:       <AlertCircle className="h-[18px] w-[18px] text-text-dim" strokeWidth={1.5} />,
    leftBorder: '',
  },
}

export function JobsBrowser({ onJenkinsStatus, wireStatus = {} }: JobsBrowserProps) {
  const [jobs,       setJobs]       = useState<JenkinsJob[]>([])
  const [loading,    setLoading]    = useState(false)
  const [triggering, setTriggering] = useState<string | null>(null)
  const [error,      setError]      = useState('')

  async function loadJobs() {
    setLoading(true); setError('')
    try {
      const res  = await fetch('/api/jobs')
      const data = await res.json()
      const list = Array.isArray(data) ? data : (data.jobs ?? [])
      setJobs(list)
      onJenkinsStatus?.(list.length >= 0 ? 'connected' : 'unknown')
    } catch {
      setError('Could not reach Jenkins — check credentials in Settings.')
      onJenkinsStatus?.('disconnected')
    } finally { setLoading(false) }
  }

  async function triggerJob(name: string) {
    setTriggering(name)
    try {
      await fetch('/api/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_name: name }),
      })
    } finally {
      setTriggering(null)
      setTimeout(loadJobs, 2000)
    }
  }

  useEffect(() => { loadJobs() }, [])

  const passing = jobs.filter(j => j.status === 'success').length
  const failing  = jobs.filter(j => j.status === 'failure').length
  const running  = jobs.filter(j => j.status === 'running').length

  return (
    <div className="flex flex-col h-full bg-bg">
      {/* Header */}
      <div className="px-6 py-5 border-b border-accent-border/40 shrink-0 bg-surface">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-[16px] font-extrabold text-text-primary tracking-tight">Jenkins Jobs</h2>
            <p className="text-[12px] font-mono text-text-muted mt-1">
              {loading ? 'Refreshing...' : `${jobs.length} job${jobs.length !== 1 ? 's' : ''} configured`}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={loadJobs}
            disabled={loading}
            className="text-text-muted hover:text-text-primary border border-accent-border/40 rounded-lg h-8 w-8"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} strokeWidth={1.5} />
          </Button>
        </div>
        {jobs.length > 0 && (
          <div className="flex items-center gap-2">
            {passing > 0 && (
              <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-success-dim text-success border border-success-border">
                {passing} passing
              </span>
            )}
            {failing > 0 && (
              <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-error-dim text-error border border-error-border">
                {failing} failing
              </span>
            )}
            {running > 0 && (
              <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-running-dim text-running border border-running-border">
                {running} running
              </span>
            )}
          </div>
        )}
      </div>

      {/* Job list */}
      <div className="flex-1 overflow-y-auto">
        {loading && jobs.length === 0 ? (
          <div className="flex items-center justify-center h-48 gap-3 text-text-muted">
            <Loader2 className="h-5 w-5 animate-spin" strokeWidth={1.5} />
            <span className="text-[13px] font-mono">Loading jobs...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-48 gap-4 px-8 text-center">
            <AlertCircle className="h-8 w-8 text-text-dim" strokeWidth={1.5} />
            <p className="text-[13px] text-error font-mono">{error}</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-text-muted">
            <Clock className="h-8 w-8 opacity-30" strokeWidth={1.5} />
            <p className="text-[13px] font-mono">No jobs found — is Jenkins configured?</p>
          </div>
        ) : (
          <div className="divide-y divide-accent-border/25">
            {jobs.map((job, i) => {
              const cfg   = STATUS_CONFIG[job.status] ?? STATUS_CONFIG.unknown
              const wired = wireStatus[job.name] === 'ok' || wireStatus[job.name] === 'already'
              return (
                <motion.div
                  key={job.name}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.025, type: 'spring', stiffness: 400, damping: 35 }}
                  className={cn(
                    'flex items-center gap-4 px-6 py-4 transition-all duration-150 group',
                    'hover:bg-overlay/30',
                    'border-l-[3px] border-l-transparent',
                    cfg.leftBorder,
                  )}
                >
                  <div className="shrink-0">{cfg.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="text-[14px] font-mono text-text-base font-medium truncate">{job.name}</span>
                      {wired && (
                        <span className="text-[10px] font-mono text-accent bg-accent-dim border border-accent-border rounded-full px-2 py-0.5 shrink-0">
                          wired
                        </span>
                      )}
                    </div>
                    <span className={cn(
                      'inline-flex items-center text-[11px] font-mono mt-1 px-2 py-0.5 rounded-lg border',
                      cfg.labelClass
                    )}>
                      {cfg.label}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => triggerJob(job.name)}
                    disabled={triggering === job.name}
                    className="opacity-0 group-hover:opacity-100 transition-opacity text-text-muted hover:text-text-primary border border-accent-border/40 rounded-lg h-8 px-3 font-mono text-[12px] gap-1.5"
                  >
                    {triggering === job.name
                      ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Running...</>
                      : <><Play    className="h-3.5 w-3.5" strokeWidth={2} /> Trigger</>}
                  </Button>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
