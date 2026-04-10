import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, Play, Circle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { JenkinsJob } from '@/types'

const STATUS_COLORS: Record<string, string> = {
  success: 'text-success',
  failure: 'text-error',
  running: 'text-running',
  unknown: 'text-text-dim',
}

const STATUS_BADGE: Record<string, React.ComponentProps<typeof Badge>['variant']> = {
  success: 'success',
  failure: 'error',
  running: 'running',
  unknown: 'muted',
}

interface JobsBrowserProps {
  onJenkinsStatus?: (status: 'connected' | 'disconnected' | 'unknown') => void
}

export function JobsBrowser({ onJenkinsStatus }: JobsBrowserProps) {
  const [jobs, setJobs] = useState<JenkinsJob[]>([])
  const [loading, setLoading] = useState(false)
  const [triggering, setTriggering] = useState<string | null>(null)
  const [error, setError] = useState('')

  async function loadJobs() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/jobs')
      const data = await res.json()
      const list = Array.isArray(data) ? data : data.jobs ?? []
      setJobs(list)
      onJenkinsStatus?.(list.length >= 0 ? 'connected' : 'unknown')
    } catch {
      setError('Could not reach Jenkins — check credentials in Settings.')
      onJenkinsStatus?.('disconnected')
    } finally {
      setLoading(false)
    }
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

  useEffect(() => {
    loadJobs()
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <span className="text-xs font-mono text-text-muted">
          {jobs.length} job{jobs.length !== 1 ? 's' : ''}
        </span>
        <Button variant="ghost" size="icon-sm" onClick={loadJobs} disabled={loading}>
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
        </Button>
      </div>

      {/* Job list */}
      <div className="flex-1 overflow-y-auto">
        {loading && jobs.length === 0 ? (
          <div className="flex items-center justify-center h-32 gap-2 text-text-dim">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-xs">Loading jobs...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-text-dim px-4 text-center">
            <p className="text-xs text-error/80">{error}</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-text-dim">
            <p className="text-xs">No jobs found — is Jenkins configured?</p>
          </div>
        ) : (
          <div className="divide-y divide-border-subtle">
            {jobs.map((job, i) => (
              <motion.div
                key={job.name}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors group"
              >
                <Circle
                  className={cn(
                    'h-2 w-2 shrink-0',
                    STATUS_COLORS[job.status] ?? 'text-text-dim',
                    job.status === 'running' && 'animate-pulse',
                    'fill-current'
                  )}
                />

                <span className="flex-1 text-sm font-mono text-text-primary truncate">
                  {job.name}
                </span>

                <Badge
                  variant={STATUS_BADGE[job.status] ?? 'muted'}
                  className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  {job.status}
                </Badge>

                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => triggerJob(job.name)}
                  disabled={triggering === job.name}
                  title={`Trigger ${job.name}`}
                  className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  {triggering === job.name ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Play className="h-3 w-3" />
                  )}
                </Button>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
