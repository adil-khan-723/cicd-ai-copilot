import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, Play, Loader2, CheckCircle2, XCircle, AlertCircle, Clock, Plug, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { JenkinsJob } from '@/types'

interface JobsBrowserProps {
  onJenkinsStatus?: (s: 'connected' | 'disconnected' | 'unknown') => void
}

function StatusDot({ status }: { status: string }) {
  const map: Record<string, string> = {
    success:    'bg-success shadow-[0_0_6px_rgba(34,197,94,0.5)]',
    failure:    'bg-error shadow-[0_0_6px_rgba(239,68,68,0.5)]',
    running:    'bg-accent dot-pulse',
    unknown:    'bg-text-dim',
  }
  return <span className={cn('inline-block h-2 w-2 rounded-full shrink-0', map[status] ?? map.unknown)} />
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'success') return <CheckCircle2 className="h-3.5 w-3.5 text-success" strokeWidth={2} />
  if (status === 'failure') return <XCircle      className="h-3.5 w-3.5 text-error"   strokeWidth={2} />
  if (status === 'running') return <Loader2      className="h-3.5 w-3.5 text-accent animate-spin" strokeWidth={2} />
  return <AlertCircle className="h-3.5 w-3.5 text-text-dim" strokeWidth={1.5} />
}

export function JobsBrowser({ onJenkinsStatus }: JobsBrowserProps) {
  const [jobs,      setJobs]      = useState<JenkinsJob[]>([])
  const [loading,   setLoading]   = useState(false)
  const [triggering,setTriggering]= useState<string | null>(null)
  const [wiring,    setWiring]    = useState<string | null>(null)
  const [wireStatus,setWireStatus]= useState<Record<string, 'ok' | 'already' | 'err'>>({})
  const [error,     setError]     = useState('')

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

  async function wireJob(name: string) {
    setWiring(name)
    try {
      const res  = await fetch('/api/inject-webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_name: name }),
      })
      const data = await res.json()
      setWireStatus(prev => ({ ...prev, [name]: data.ok ? (data.already ? 'already' : 'ok') : 'err' }))
    } catch {
      setWireStatus(prev => ({ ...prev, [name]: 'err' }))
    } finally {
      setWiring(null)
    }
  }

  useEffect(() => { loadJobs() }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-glass shrink-0">
        <span className="text-xs font-mono text-text-muted">
          {loading ? 'Loading...' : `${jobs.length} job${jobs.length !== 1 ? 's' : ''}`}
        </span>
        <Button variant="ghost" size="icon-sm" onClick={loadJobs} disabled={loading} title="Refresh">
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} strokeWidth={1.5} />
        </Button>
      </div>

      {/* Job list */}
      <div className="flex-1 overflow-y-auto">
        {loading && jobs.length === 0 ? (
          <div className="flex items-center justify-center h-40 gap-2 text-text-dim">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
            <span className="text-xs font-mono">Loading jobs...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-40 gap-3 px-6 text-center">
            <AlertCircle className="h-6 w-6 text-text-dim" strokeWidth={1.5} />
            <p className="text-xs text-error/80">{error}</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 gap-2 text-text-dim">
            <Clock className="h-6 w-6 opacity-30" strokeWidth={1.5} />
            <p className="text-xs">No jobs found — is Jenkins configured?</p>
          </div>
        ) : (
          <div className="divide-y divide-glass">
            {jobs.map((job, i) => (
              <motion.div
                key={job.name}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03, type: 'spring', stiffness: 400, damping: 35 }}
                className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.025] transition-colors duration-150 group"
              >
                <StatusDot status={job.status} />

                <div className="flex-1 min-w-0">
                  <span className="text-sm font-mono text-text-primary truncate block">
                    {job.name}
                  </span>
                </div>

                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                  <StatusIcon status={job.status} />

                  {/* Wire-up button */}
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => wireJob(job.name)}
                    disabled={wiring === job.name || wireStatus[job.name] === 'ok' || wireStatus[job.name] === 'already'}
                    title={
                      wireStatus[job.name] === 'ok'      ? 'Webhook injected' :
                      wireStatus[job.name] === 'already'  ? 'Already wired up' :
                      wireStatus[job.name] === 'err'      ? 'Injection failed — retry' :
                      'Inject webhook notifications'
                    }
                    className={cn(
                      wireStatus[job.name] === 'ok'     && 'text-success',
                      wireStatus[job.name] === 'already' && 'text-success opacity-50',
                      wireStatus[job.name] === 'err'     && 'text-error',
                    )}
                  >
                    {wiring === job.name
                      ? <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
                      : wireStatus[job.name] === 'ok' || wireStatus[job.name] === 'already'
                        ? <Zap className="h-3 w-3" strokeWidth={2} />
                        : <Plug className="h-3 w-3" strokeWidth={2} />}
                  </Button>

                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => triggerJob(job.name)}
                    disabled={triggering === job.name}
                    title={`Trigger ${job.name}`}
                  >
                    {triggering === job.name
                      ? <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
                      : <Play    className="h-3 w-3" strokeWidth={2} />}
                  </Button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
