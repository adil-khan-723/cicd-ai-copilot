import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, GitBranch, ChevronRight, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const _CRED_KEYWORDS = /CRED|SECRET|KEY|TOKEN|PASS|SSH|CERT|AUTH/i

// Detect YOUR_* placeholders that are NOT credential IDs — those go to MissingCredentialModal
function detectPlaceholders(code: string): string[] {
  const matches = code.match(/\bYOUR_[A-Z][A-Z0-9_]*\b/g) ?? []
  return [...new Set(matches)].filter(p => !_CRED_KEYWORDS.test(p))
}

// Detect YOUR_* placeholders that ARE credential IDs — returned to parent after commit
function detectCredPlaceholders(code: string): string[] {
  const matches = code.match(/\bYOUR_[A-Z][A-Z0-9_]*\b/g) ?? []
  return [...new Set(matches)].filter(p => _CRED_KEYWORDS.test(p))
}

function substituteValues(code: string, values: Record<string, string>): string {
  let result = code
  for (const [key, val] of Object.entries(values)) {
    result = result.replaceAll(key, val)
  }
  return result
}

type Step =
  | { kind: 'placeholder'; key: string; index: number; total: number }
  | { kind: 'jobname' }
  | { kind: 'review'; finalCode: string }

export interface PendingCredential {
  credentialId: string   // actual ID to create in Jenkins (editable by user)
  placeholder?: string   // YOUR_* key it came from, shown as hint
}

interface Props {
  open: boolean
  pipeline: string
  platform: 'jenkins' | 'github'
  description: string
  onCommitted: (pendingCredentials: PendingCredential[]) => void
  onCancel: () => void
}

export function PipelineCommitModal({ open, pipeline, platform, description, onCommitted, onCancel }: Props) {
  const [values, setValues]     = useState<Record<string, string>>({})
  const [jobName, setJobName]   = useState('')
  const [stepIdx, setStepIdx]   = useState(0)
  const [inputVal, setInputVal] = useState('')
  const [committing, setCommitting] = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null) as React.RefObject<HTMLInputElement>

  const placeholders = detectPlaceholders(pipeline)

  const steps: Step[] = [
    ...placeholders.map((key, i) => ({ kind: 'placeholder' as const, key, index: i, total: placeholders.length })),
    { kind: 'jobname' as const },
    { kind: 'review' as const, finalCode: substituteValues(pipeline, values) },
  ]

  const currentStep = steps[stepIdx]

  useEffect(() => {
    if (open) { setValues({}); setJobName(''); setStepIdx(0); setInputVal(''); setError(null) }
  }, [open])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 80)
  }, [open, stepIdx])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onCancel])

  function advance() {
    if (!inputVal.trim()) return
    if (currentStep.kind === 'placeholder') {
      setValues(v => ({ ...v, [currentStep.key]: inputVal.trim() }))
    } else if (currentStep.kind === 'jobname') {
      setJobName(inputVal.trim())
    }
    setInputVal('')
    setStepIdx(i => i + 1)
  }

  async function handleApprove() {
    setCommitting(true)
    setError(null)
    const finalCode = substituteValues(pipeline, values)
    try {
      const res = await fetch('/api/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform,
          content:          finalCode,
          description,
          apply_to_jenkins: platform === 'jenkins',
          job_name:         jobName,
        }),
      })
      const data = await res.json()
      if (data.success) {
        // Credential placeholders left unsubstituted (YOUR_SSH_CREDS etc) become pending creds
        // with a suggested ID derived from the placeholder name.
        const credPlaceholders = detectCredPlaceholders(pipeline)
        const fromPlaceholders: PendingCredential[] = credPlaceholders.map(p => ({
          credentialId: p.replace(/^YOUR_/, '').toLowerCase().replace(/_/g, '-'),
          placeholder: p,
        }))
        // Backend-detected missing creds (already existing IDs that don't exist in Jenkins)
        const fromBackend: PendingCredential[] = (data.missing_credentials ?? [] as string[])
          .filter((id: string) => !fromPlaceholders.some(p => p.credentialId === id))
          .map((id: string) => ({ credentialId: id }))
        const pending = [...fromPlaceholders, ...fromBackend]
        onCommitted(pending)
      } else {
        setError(data.detail ?? 'Commit failed')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Network error')
    } finally {
      setCommitting(false)
    }
  }

  const progressPct = steps.length > 1 ? (stepIdx / (steps.length - 1)) * 100 : 100

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-40 bg-[#1c1410]/40 backdrop-blur-[6px]"
            onClick={onCancel}
          />

          <motion.div
            key="modal"
            role="dialog" aria-modal="true" aria-labelledby="commit-modal-title"
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ type: 'spring', stiffness: 480, damping: 36 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
          >
            <div
              className="pointer-events-auto w-full max-w-[540px] rounded-2xl bg-white shadow-modal border border-[rgba(46,109,160,0.14)] overflow-hidden flex flex-col"
              onClick={e => e.stopPropagation()}
            >
              {/* Accent bar + progress */}
              <div className="h-[3px] w-full bg-[rgba(46,109,160,0.12)] flex-shrink-0">
                <motion.div
                  className="h-full bg-[#2e6da0]"
                  animate={{ width: `${progressPct}%` }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                />
              </div>

              {/* Header */}
              <div className="flex items-start gap-3.5 px-5 pt-5 pb-4 border-b border-[rgba(46,109,160,0.1)]">
                <div className="shrink-0 w-10 h-10 rounded-xl flex items-center justify-center bg-[rgba(46,109,160,0.06)] border border-[rgba(46,109,160,0.12)] text-[#2e6da0]">
                  <GitBranch className="h-5 w-5" strokeWidth={1.8} />
                </div>
                <div className="flex-1 min-w-0">
                  <h2 id="commit-modal-title" className="text-[15px] font-semibold text-text-primary leading-tight">
                    Commit Pipeline to Jenkins
                  </h2>
                  <p className="text-[12px] text-text-dim mt-0.5 truncate">{description}</p>
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
              <AnimatePresence mode="wait">
                <motion.div
                  key={stepIdx}
                  initial={{ opacity: 0, x: 18 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -18 }}
                  transition={{ duration: 0.16 }}
                  className="px-5 py-5 space-y-4 overflow-y-auto max-h-[60vh]"
                >
                  {currentStep.kind === 'placeholder' && (
                    <PlaceholderStep
                      stepKey={currentStep.key}
                      index={currentStep.index}
                      total={currentStep.total}
                      value={inputVal}
                      onChange={setInputVal}
                      onNext={advance}
                      inputRef={inputRef}
                    />
                  )}

                  {currentStep.kind === 'jobname' && (
                    <JobNameStep
                      value={inputVal}
                      onChange={setInputVal}
                      onNext={advance}
                      inputRef={inputRef}
                    />
                  )}

                  {currentStep.kind === 'review' && (
                    <ReviewStep
                      code={substituteValues(pipeline, values)}
                      jobName={jobName}
                      error={error}
                    />
                  )}
                </motion.div>
              </AnimatePresence>

              {/* Footer */}
              <div className="flex items-center justify-between gap-3 px-5 py-4 border-t border-[rgba(46,109,160,0.1)] bg-[#f9fbfd]">
                <button
                  onClick={onCancel}
                  className="h-9 px-5 rounded-xl text-[13px] font-semibold font-sans border border-[rgba(46,109,160,0.18)] text-text-muted bg-white hover:bg-overlay/60 hover:text-text-base transition-all duration-150 cursor-pointer"
                >
                  Cancel
                </button>

                {currentStep.kind !== 'review' ? (
                  <button
                    onClick={advance}
                    disabled={!inputVal.trim()}
                    className={cn(
                      'h-9 px-6 rounded-xl text-[13px] font-bold font-sans flex items-center gap-2 text-white transition-all duration-150 cursor-pointer active:scale-[0.98]',
                      inputVal.trim() ? 'bg-[#2e6da0] hover:bg-[#265d8c]' : 'bg-[#2e6da0]/40 cursor-not-allowed',
                    )}
                  >
                    Next <ChevronRight className="h-3.5 w-3.5" strokeWidth={2.5} />
                  </button>
                ) : (
                  <button
                    onClick={handleApprove}
                    disabled={committing}
                    className="h-9 px-6 rounded-xl text-[13px] font-bold font-sans flex items-center gap-2 text-white bg-[#2e6da0] hover:bg-[#265d8c] transition-all duration-150 cursor-pointer active:scale-[0.98] disabled:opacity-60"
                  >
                    {committing
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />}
                    Approve &amp; Send to Jenkins
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ── sub-steps ─────────────────────────────────────────────────────────────────

function PlaceholderStep({ stepKey, index, total, value, onChange, onNext, inputRef }: {
  stepKey: string; index: number; total: number
  value: string; onChange: (v: string) => void
  onNext: () => void; inputRef: React.RefObject<HTMLInputElement>
}) {
  const meta = getPlaceholderMeta(stepKey)

  return (
    <div className="space-y-4">
      <span className="text-[10px] font-mono font-semibold text-[#2e6da0] uppercase tracking-[0.12em]">
        Variable {index + 1} of {total}
      </span>

      <div className="rounded-xl border border-[rgba(46,109,160,0.12)] bg-[#f0f6fb] px-4 py-3.5 space-y-1">
        <p className="text-[10px] font-mono text-text-dim uppercase tracking-[0.1em]">
          {meta.category}
        </p>
        <p className="text-[14px] font-semibold text-text-primary">{meta.label}</p>
        {meta.description && (
          <p className="text-[11px] text-text-dim">{meta.description}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <input
          ref={inputRef}
          type={meta.inputType}
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') onNext() }}
          placeholder={meta.hint}
          className="w-full h-9 rounded-lg border border-[rgba(46,109,160,0.2)] bg-white px-3 text-[13px] font-mono text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-[#2e6da0]/30 focus:border-[#2e6da0]/50 transition"
        />
        <p className="text-[11px] text-text-dim">Press Enter or click Next to continue</p>
      </div>
    </div>
  )
}

function JobNameStep({ value, onChange, onNext, inputRef }: {
  value: string; onChange: (v: string) => void
  onNext: () => void; inputRef: React.RefObject<HTMLInputElement>
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-[rgba(46,109,160,0.12)] bg-[#f0f6fb] px-4 py-3.5">
        <p className="text-[13px] text-text-base leading-relaxed">
          What should this Jenkins job be called?
        </p>
        <p className="text-[11px] font-mono text-text-dim mt-1">Use lowercase letters, numbers, and hyphens</p>
      </div>
      <div className="space-y-1.5">
        <label className="text-[12px] font-semibold text-text-muted">Jenkins Job Name</label>
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') onNext() }}
          placeholder="e.g. python-ecr-pipeline"
          className="w-full h-9 rounded-lg border border-[rgba(46,109,160,0.2)] bg-white px-3 text-[13px] font-mono text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-[#2e6da0]/30 focus:border-[#2e6da0]/50 transition"
        />
      </div>
    </div>
  )
}

function ReviewStep({ code, jobName, error }: { code: string; jobName: string; error: string | null }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.12em]">
          Review generated Jenkinsfile
        </p>
        <span className="font-mono text-[11px] text-[#2e6da0] bg-[rgba(46,109,160,0.08)] border border-[rgba(46,109,160,0.15)] rounded-md px-2 py-0.5">
          {jobName}
        </span>
      </div>

      <div className="rounded-xl border border-[rgba(46,109,160,0.12)] overflow-hidden">
        <div className="px-3 py-1.5 bg-[rgba(46,109,160,0.06)] border-b border-[rgba(46,109,160,0.1)] flex items-center gap-2">
          <span className="text-[10px] font-mono text-text-dim uppercase tracking-widest">groovy</span>
        </div>
        <pre className="px-3 py-2.5 text-[11px] font-mono text-text-primary bg-white overflow-x-auto leading-relaxed whitespace-pre max-h-[280px]">
          {code}
        </pre>
      </div>

      <div className="flex items-start gap-2.5 rounded-xl border border-[rgba(176,125,42,0.2)] bg-warning-dim px-3.5 py-3">
        <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" strokeWidth={2} />
        <p className="text-[12px] text-warning leading-relaxed">
          This will create or update the Jenkins job <strong>{jobName}</strong> and cannot be automatically undone.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-[12px] text-red-600">
          {error}
        </div>
      )}
    </div>
  )
}

interface PlaceholderMeta {
  label: string
  category: string
  description?: string
  hint: string
  inputType: 'text' | 'url' | 'number'
}

const _PLACEHOLDER_MAP: Record<string, PlaceholderMeta> = {
  // Source control
  YOUR_REPO_URL:               { label: 'GitHub Repository URL',      category: 'Source Control', description: 'Full HTTPS clone URL of your repository', hint: 'https://github.com/org/repo.git', inputType: 'url' },
  YOUR_BRANCH:                 { label: 'Branch to build',            category: 'Source Control', hint: 'main', inputType: 'text' },
  YOUR_GIT_BRANCH:             { label: 'Branch to build',            category: 'Source Control', hint: 'main', inputType: 'text' },

  // Docker / registry
  YOUR_DOCKERHUB_USERNAME:     { label: 'DockerHub Username',         category: 'Docker', hint: 'myusername', inputType: 'text' },
  YOUR_DOCKERHUB_IMAGE_NAME:   { label: 'Docker Image Name',          category: 'Docker', hint: 'my-app', inputType: 'text' },
  YOUR_IMAGE_NAME:             { label: 'Docker Image Name',          category: 'Docker', hint: 'my-app', inputType: 'text' },
  YOUR_DOCKER_IMAGE:           { label: 'Docker Base Image',          category: 'Docker', hint: 'node:18-alpine', inputType: 'text' },
  YOUR_REGISTRY:               { label: 'Container Registry URL',     category: 'Docker', hint: 'registry.example.com', inputType: 'text' },
  YOUR_ECR_REPO:               { label: 'AWS ECR Repository URI',     category: 'AWS', hint: '123456789.dkr.ecr.us-east-1.amazonaws.com/my-app', inputType: 'text' },

  // AWS
  YOUR_AWS_REGION:             { label: 'AWS Region',                 category: 'AWS', hint: 'us-east-1', inputType: 'text' },
  YOUR_AWS_ACCOUNT_ID:         { label: 'AWS Account ID',             category: 'AWS', hint: '123456789012', inputType: 'text' },

  // Remote server / SSH
  YOUR_REMOTE_SERVER_IP:       { label: 'Remote Server IP',           category: 'Deployment', hint: '192.168.1.100', inputType: 'text' },
  YOUR_SERVER_IP:              { label: 'Remote Server IP',           category: 'Deployment', hint: '192.168.1.100', inputType: 'text' },
  YOUR_REMOTE_SERVER_USERNAME: { label: 'SSH Login Username',         category: 'Deployment', hint: 'ubuntu', inputType: 'text' },
  YOUR_SSH_USER:               { label: 'SSH Login Username',         category: 'Deployment', hint: 'ubuntu', inputType: 'text' },
  YOUR_REMOTE_DEPLOY_PATH:     { label: 'Deployment Directory',       category: 'Deployment', description: 'Absolute path on the remote server', hint: '/opt/myapp', inputType: 'text' },
  YOUR_DEPLOY_PATH:            { label: 'Deployment Directory',       category: 'Deployment', hint: '/opt/myapp', inputType: 'text' },

  // App config
  YOUR_CONTAINER_NAME:         { label: 'Docker Container Name',      category: 'App Config', hint: 'my-app-container', inputType: 'text' },
  YOUR_APP_NAME:               { label: 'Application Name',           category: 'App Config', hint: 'my-app', inputType: 'text' },
  YOUR_APP_PORT:               { label: 'Application Port',           category: 'App Config', hint: '8080', inputType: 'number' },
}

function getPlaceholderMeta(key: string): PlaceholderMeta {
  if (_PLACEHOLDER_MAP[key]) return _PLACEHOLDER_MAP[key]
  // Generic fallback: derive readable label from key
  const raw = key.replace(/^YOUR_/, '').replace(/_/g, ' ').toLowerCase()
  const label = raw.replace(/\b\w/g, c => c.toUpperCase())
  return { label, category: 'Configuration', hint: 'your-value', inputType: 'text' }
}
