import { motion } from 'framer-motion'
import { CheckCircle2, XCircle, Loader2, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepStatus } from '@/types'

const STAGE_LABELS: Record<string, string> = {
  WEBHOOK_RECEIVED: 'Webhook',
  LOG_EXTRACTED: 'Extract',
  TOOL_VERIFICATION: 'Verify',
  CONTEXT_BUILT: 'Context',
  LLM_ANALYSIS: 'Analyze',
}

interface Stage {
  stage: string
  status: StepStatus
  detail?: string
}

interface StageGraphProps {
  stages: Stage[]
}

function StatusIcon({ status }: { status: StepStatus }) {
  if (status === 'done')
    return <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0" />
  if (status === 'failed')
    return <XCircle className="h-3.5 w-3.5 text-error shrink-0" />
  if (status === 'running')
    return <Loader2 className="h-3.5 w-3.5 text-running shrink-0 animate-spin" />
  return <Circle className="h-3.5 w-3.5 text-text-dim shrink-0" />
}

export function StageGraph({ stages }: StageGraphProps) {
  if (stages.length === 0) return null

  return (
    <div className="flex items-start gap-0 overflow-x-auto pb-1">
      {stages.map((s, i) => (
        <div key={s.stage} className="flex items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05 }}
            className={cn(
              'flex flex-col items-center gap-1 px-2 py-1.5 rounded',
              'min-w-[72px] cursor-default',
              s.status === 'running' && 'bg-running/5',
              s.status === 'done' && 'bg-success/5',
              s.status === 'failed' && 'bg-error/5',
            )}
            title={s.detail}
          >
            <StatusIcon status={s.status} />
            <span
              className={cn(
                'text-[10px] font-mono text-center leading-tight',
                s.status === 'done' ? 'text-success/80' :
                s.status === 'failed' ? 'text-error/80' :
                s.status === 'running' ? 'text-running/80' :
                'text-text-dim'
              )}
            >
              {STAGE_LABELS[s.stage] ?? s.stage}
            </span>
          </motion.div>

          {/* Connector line */}
          {i < stages.length - 1 && (
            <div
              className={cn(
                'h-px w-4 shrink-0',
                stages[i + 1].status === 'pending' ? 'bg-border' : 'bg-text-dim'
              )}
            />
          )}
        </div>
      ))}
    </div>
  )
}
