import { motion } from 'framer-motion'
import { CheckCircle2, XCircle, Loader2, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepStatus } from '@/types'

const STAGE_LABELS: Record<string, string> = {
  WEBHOOK_RECEIVED: 'Webhook',
  LOG_EXTRACTED:    'Extract',
  TOOL_VERIFICATION:'Verify',
  CONTEXT_BUILT:    'Context',
  LLM_ANALYSIS:     'Analyze',
}

interface Stage {
  stage:   string
  status:  StepStatus
  detail?: string
}

function StatusIcon({ status }: { status: StepStatus }) {
  if (status === 'done')
    return <CheckCircle2 className="h-3.5 w-3.5 text-success" strokeWidth={2} />
  if (status === 'failed')
    return <XCircle className="h-3.5 w-3.5 text-error" strokeWidth={2} />
  if (status === 'running')
    return <Loader2 className="h-3.5 w-3.5 text-accent animate-spin" strokeWidth={2} />
  return <Circle className="h-3.5 w-3.5 text-text-dim" strokeWidth={1.5} />
}

export function StageGraph({ stages }: { stages: Stage[] }) {
  if (!stages.length) return null

  return (
    <div className="flex items-center gap-0 overflow-x-auto">
      {stages.map((s, i) => (
        <div key={s.stage} className="flex items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.06, type: 'spring', stiffness: 400, damping: 28 }}
            title={s.detail}
            className={cn(
              'flex flex-col items-center gap-1.5 px-2.5 py-2 rounded-md min-w-[68px] cursor-default transition-colors duration-150',
              s.status === 'running' && 'bg-accent-dim',
              s.status === 'done'    && 'bg-success-dim',
              s.status === 'failed'  && 'bg-error-dim',
              s.status === 'pending' && 'bg-transparent',
            )}
          >
            <StatusIcon status={s.status} />
            <span className={cn(
              'text-[10px] font-mono font-medium text-center leading-none',
              s.status === 'done'    && 'text-success',
              s.status === 'failed'  && 'text-error',
              s.status === 'running' && 'text-accent-hi',
              s.status === 'pending' && 'text-text-dim',
            )}>
              {STAGE_LABELS[s.stage] ?? s.stage}
            </span>
          </motion.div>

          {i < stages.length - 1 && (
            <div className={cn(
              'h-px w-4 shrink-0 transition-colors duration-300',
              stages[i + 1].status !== 'pending' ? 'bg-border-hi' : 'bg-border'
            )} />
          )}
        </div>
      ))}
    </div>
  )
}
