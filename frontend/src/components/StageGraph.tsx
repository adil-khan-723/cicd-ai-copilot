import { motion } from 'framer-motion'
import { CheckCircle2, XCircle, Loader2, Circle, SkipForward } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StepStatus, PipelineStage } from '@/types'

// ── Agent processing steps (internal pipeline) ────────────────────────────

const AGENT_STAGE_LABELS: Record<string, string> = {
  WEBHOOK_RECEIVED:  'Webhook',
  LOG_EXTRACTED:     'Extract',
  TOOL_VERIFICATION: 'Verify',
  CONTEXT_BUILT:     'Context',
  LLM_ANALYSIS:      'Analyze',
}

interface AgentStep {
  stage:   string
  status:  StepStatus
  detail?: string
}

function AgentStatusIcon({ status }: { status: StepStatus }) {
  if (status === 'done')    return <CheckCircle2 className="h-3.5 w-3.5 text-success"     strokeWidth={2} />
  if (status === 'failed')  return <XCircle      className="h-3.5 w-3.5 text-error"       strokeWidth={2} />
  if (status === 'running') return <Loader2      className="h-3.5 w-3.5 text-accent animate-spin" strokeWidth={2} />
  return <Circle className="h-3.5 w-3.5 text-text-dim" strokeWidth={1.5} />
}

export function AgentStepRow({ stages }: { stages: AgentStep[] }) {
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
            )}
          >
            <AgentStatusIcon status={s.status} />
            <span className={cn(
              'text-[10px] font-mono font-medium text-center leading-none',
              s.status === 'done'    && 'text-success',
              s.status === 'failed'  && 'text-error',
              s.status === 'running' && 'text-accent-hi',
              s.status === 'pending' && 'text-text-dim',
            )}>
              {AGENT_STAGE_LABELS[s.stage] ?? s.stage}
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

// ── Jenkins / GHA pipeline stages ─────────────────────────────────────────

function PipelineStatusIcon({ status }: { status: PipelineStage['status'] }) {
  if (status === 'passed')  return <CheckCircle2 className="h-3.5 w-3.5 text-success"  strokeWidth={2} />
  if (status === 'failed')  return <XCircle      className="h-3.5 w-3.5 text-error"    strokeWidth={2} />
  return <SkipForward className="h-3.5 w-3.5 text-text-dim" strokeWidth={1.5} />
}

export function PipelineStageRow({ stages, onStageClick }: { stages: PipelineStage[]; onStageClick?: (stage: PipelineStage) => void }) {
  if (!stages.length) return null
  return (
    <div className="flex items-center gap-0 overflow-x-auto">
      {stages.map((s, i) => (
        <div key={s.name} className="flex items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05, type: 'spring', stiffness: 400, damping: 28 }}
            onClick={() => onStageClick?.(s)}
            className={cn(
              'flex flex-col items-center gap-1.5 px-2.5 py-2 rounded-md min-w-[72px] transition-colors duration-150',
              onStageClick ? 'cursor-pointer hover:ring-1 hover:ring-accent-border' : 'cursor-default',
              s.status === 'passed'  && 'bg-success-dim',
              s.status === 'failed'  && 'bg-error-dim',
              s.status === 'skipped' && 'opacity-40',
            )}
          >
            <PipelineStatusIcon status={s.status} />
            <span className={cn(
              'text-[10px] font-mono font-medium text-center leading-none max-w-[80px] truncate',
              s.status === 'passed'  && 'text-success',
              s.status === 'failed'  && 'text-error',
              s.status === 'skipped' && 'text-text-dim',
            )}
              title={s.name}
            >
              {s.name}
            </span>
          </motion.div>
          {i < stages.length - 1 && (
            <div className={cn(
              'h-px w-3 shrink-0',
              s.status === 'passed' ? 'bg-border-hi' : 'bg-border'
            )} />
          )}
        </div>
      ))}
    </div>
  )
}

// Keep old export name for any existing imports
export { AgentStepRow as StageGraph }
