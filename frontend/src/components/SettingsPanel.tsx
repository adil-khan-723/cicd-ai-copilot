import { useState, useEffect } from 'react'
import { Settings, Server, Brain, Webhook, ExternalLink, ClipboardList, RefreshCw, CheckCircle2, AlertTriangle, Circle, Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface SettingSection {
  icon: React.ElementType
  title: string
  desc: string
  items: { label: string; value: string }[]
}

const SECTIONS: SettingSection[] = [
  {
    icon: Server,
    title: 'Jenkins',
    desc: 'Build server connection',
    items: [
      { label: 'Endpoint', value: 'Configured in .env' },
      { label: 'Webhook', value: 'POST /webhook/jenkins-notification' },
      { label: 'Setup', value: './start.sh --setup-jenkins' },
    ],
  },
  {
    icon: Brain,
    title: 'LLM Provider',
    desc: 'Analysis and generation model',
    items: [
      { label: 'Analysis', value: 'claude-haiku / llama3.1:8b' },
      { label: 'Generation', value: 'claude-sonnet / qwen2.5-coder' },
      { label: 'Switch', value: 'LLM_PROVIDER in .env' },
    ],
  },
  {
    icon: Webhook,
    title: 'Webhooks',
    desc: 'Event endpoints',
    items: [
      { label: 'Jenkins', value: 'POST /webhook/jenkins-notification' },
      { label: 'Pipeline Failure', value: 'POST /webhook/pipeline-failure' },
      { label: 'SSE Stream', value: 'GET /api/stream' },
    ],
  },
]

export function SettingsPanel({ onOpenSetup }: { onOpenSetup: () => void }) {
  return (
    <div className="h-full overflow-y-auto bg-bg">
      <div className="max-w-2xl mx-auto px-8 py-10">

        {/* Header */}
        <div className="mb-8">
          <h2 className="text-[22px] font-extrabold text-text-primary tracking-tight">Configuration</h2>
          <p className="text-[13px] font-mono text-text-muted mt-2 leading-relaxed">
            Credentials and integrations are managed in{' '}
            <code className="font-mono text-accent bg-accent-dim border border-accent-border rounded-md px-1.5 py-0.5 text-[12px]">.env</code>
            {'. '}Use the setup wizard to update connection settings.
          </p>
        </div>

        {/* Setup CTA */}
        <div className="rounded-2xl border border-accent-border bg-gradient-to-r from-overlay to-card-hi px-5 py-5 flex items-center justify-between mb-8 shadow-soft">
          <div>
            <p className="text-[15px] font-bold text-text-primary tracking-tight">Project Setup Wizard</p>
            <p className="text-[12px] font-mono text-text-muted mt-1">
              Update Jenkins URL, GitHub token, or LLM credentials
            </p>
          </div>
          <Button
            size="sm"
            onClick={onOpenSetup}
            className="gap-2 bg-gradient-accent hover:opacity-90 text-white font-semibold border-0 text-[13px] h-9 px-4 font-mono rounded-xl shadow-soft"
          >
            <Settings className="h-3.5 w-3.5" strokeWidth={2} />
            Open Wizard
          </Button>
        </div>

        {/* Sections */}
        <div className="space-y-4">
          {SECTIONS.map(({ icon: Icon, title, desc, items }) => (
            <div
              key={title}
              className="rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card"
            >
              {/* Section header */}
              <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
                  <Icon className="h-4 w-4 text-accent" strokeWidth={1.75} />
                </div>
                <div>
                  <p className="text-[14px] font-bold text-text-primary leading-none">{title}</p>
                  <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">{desc}</p>
                </div>
              </div>
              {/* Rows */}
              <div className="divide-y divide-accent-border/20">
                {items.map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between px-5 py-3.5 hover:bg-overlay/20 transition-colors">
                    <span className="text-[12px] font-mono text-text-muted">{label}</span>
                    <span className="text-[12px] font-mono text-text-base text-right max-w-[55%] truncate">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* LLM Status */}
        <LlmStatus />

        {/* Security Status */}
        <SecurityStatus />

        {/* Audit Log */}
        <AuditLog />

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-accent-border/30 flex items-center gap-6">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-[12px] font-mono text-text-muted hover:text-accent transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
            API Docs
          </a>
          <a
            href="http://localhost:8000/webhook/test"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-[12px] font-mono text-text-muted hover:text-accent transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
            Test Webhook
          </a>
        </div>
      </div>
    </div>
  )
}

type ProviderStatus = 'checking' | 'ok' | 'warn' | 'off'

function LlmStatus() {
  const [anthropic, setAnthropic] = useState<ProviderStatus>('checking')
  const [ollama,    setOllama]    = useState<ProviderStatus>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(d => setAnthropic(d?.ok ? 'ok' : 'warn'))
      .catch(() => setAnthropic('warn'))

    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 3000)
    fetch('http://localhost:11434/api/tags', { signal: ctrl.signal })
      .then(r => { clearTimeout(timer); setOllama(r.ok ? 'ok' : 'off') })
      .catch(() => { clearTimeout(timer); setOllama('off') })
  }, [])

  function StatusDot({ status, label, sublabel }: { status: ProviderStatus; label: string; sublabel: string }) {
    return (
      <div className="flex items-center justify-between px-5 py-3.5 hover:bg-overlay/20 transition-colors">
        <div>
          <span className="text-[12px] font-mono text-text-base">{label}</span>
          <p className="text-[11px] font-mono text-text-dim mt-0.5">{sublabel}</p>
        </div>
        <div className="flex items-center gap-1.5">
          {status === 'checking' && <Circle className="h-3.5 w-3.5 text-text-dim animate-pulse" strokeWidth={1.5} />}
          {status === 'ok'       && <CheckCircle2 className="h-3.5 w-3.5 text-success" strokeWidth={2} />}
          {status === 'warn'     && <AlertTriangle className="h-3.5 w-3.5 text-warning" strokeWidth={2} />}
          {status === 'off'      && <Circle className="h-3.5 w-3.5 text-text-dim" strokeWidth={1.5} />}
          <span className={cn('text-[11px] font-mono', {
            'text-text-dim': status === 'checking' || status === 'off',
            'text-success':  status === 'ok',
            'text-warning':  status === 'warn',
          })}>
            {status === 'checking' ? 'checking…'
              : status === 'ok'   ? 'connected'
              : status === 'warn' ? 'not configured'
              : 'not running'}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-6 rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
          <Brain className="h-4 w-4 text-accent" strokeWidth={1.75} />
        </div>
        <div>
          <p className="text-[14px] font-bold text-text-primary leading-none">LLM Status</p>
          <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">Live provider availability</p>
        </div>
      </div>
      <div className="divide-y divide-accent-border/20">
        <StatusDot status={anthropic} label="Anthropic" sublabel="claude-haiku / claude-sonnet" />
        <StatusDot status={ollama}    label="Ollama"    sublabel="localhost:11434" />
      </div>
    </div>
  )
}

function SecurityStatus() {
  const [webhookSet, setWebhookSet] = useState<boolean | null>(null)

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(d => setWebhookSet(d?.webhook_secret_set ?? false))
      .catch(() => setWebhookSet(false))
  }, [])

  type RowStatus = 'checking' | 'ok' | 'warn'

  function SecurityRow({ label, sublabel, status }: { label: string; sublabel: string; status: RowStatus }) {
    return (
      <div className="flex items-center justify-between px-5 py-3.5 hover:bg-overlay/20 transition-colors">
        <div>
          <span className="text-[12px] font-mono text-text-base">{label}</span>
          <p className="text-[11px] font-mono text-text-dim mt-0.5">{sublabel}</p>
        </div>
        <div className="flex items-center gap-1.5">
          {status === 'checking' && <Circle className="h-3.5 w-3.5 text-text-dim animate-pulse" strokeWidth={1.5} />}
          {status === 'ok'       && <CheckCircle2 className="h-3.5 w-3.5 text-success" strokeWidth={2} />}
          {status === 'warn'     && <AlertTriangle className="h-3.5 w-3.5 text-warning" strokeWidth={2} />}
          <span className={cn('text-[11px] font-mono', {
            'text-text-dim': status === 'checking',
            'text-success':  status === 'ok',
            'text-warning':  status === 'warn',
          })}>
            {status === 'checking' ? 'checking…' : status === 'ok' ? 'active' : 'NOT SET'}
          </span>
        </div>
      </div>
    )
  }

  const webhookStatus: RowStatus = webhookSet === null ? 'checking' : webhookSet ? 'ok' : 'warn'

  return (
    <div className="mt-6 rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
          <Shield className="h-4 w-4 text-accent" strokeWidth={1.75} />
        </div>
        <div>
          <p className="text-[14px] font-bold text-text-primary leading-none">Security</p>
          <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">Credential safety controls</p>
        </div>
      </div>
      <div className="divide-y divide-accent-border/20">
        <SecurityRow
          label="Webhook secret"
          sublabel="HMAC signature validation on incoming events"
          status={webhookStatus}
        />
        <SecurityRow
          label="Credential scrubbing"
          sublabel="Tokens redacted from all error messages and logs"
          status="ok"
        />
        <SecurityRow
          label="Audit trail"
          sublabel="Every credential access recorded (names only)"
          status="ok"
        />
      </div>
    </div>
  )
}

interface AuditEntry {
  timestamp: string
  fix_type: string
  job_name: string
  build_number: string
  result: string
}

function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    fetch('/api/audit?limit=20')
      .then(r => r.json())
      .then(data => setEntries(data.entries ?? []))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="mt-6 rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
          <ClipboardList className="h-4 w-4 text-accent" strokeWidth={1.75} />
        </div>
        <div className="flex-1">
          <p className="text-[14px] font-bold text-text-primary leading-none">Fix Audit Log</p>
          <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">Recent fix executions</p>
        </div>
        <button
          onClick={load}
          className="text-text-dim hover:text-text-primary transition-colors cursor-pointer"
          title="Refresh"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} strokeWidth={1.75} />
        </button>
      </div>
      {entries.length === 0 ? (
        <div className="px-5 py-6 text-[12px] font-mono text-text-dim text-center">
          {loading ? 'Loading…' : 'No fix executions recorded yet.'}
        </div>
      ) : (
        <div className="divide-y divide-accent-border/20">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 px-5 py-2 bg-overlay/20">
            {['Job / Build', 'Fix type', 'Result', 'Time'].map(h => (
              <span key={h} className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em]">{h}</span>
            ))}
          </div>
          {entries.map((e, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto_auto_auto] gap-3 px-5 py-2.5 hover:bg-overlay/20 transition-colors items-center">
              <span className="text-[12px] font-mono text-text-base truncate">
                {e.job_name} <span className="text-text-dim">#{e.build_number}</span>
              </span>
              <span className="text-[11px] font-mono text-text-muted">{e.fix_type}</span>
              <span className={cn(
                'text-[11px] font-mono rounded-full px-2 py-0.5 border',
                e.result === 'success'
                  ? 'text-success bg-success-dim border-success-border'
                  : 'text-error bg-error-dim border-error-border',
              )}>
                {e.result}
              </span>
              <span className="text-[10px] font-mono text-text-dim whitespace-nowrap">
                {new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
