import { useState, useEffect } from 'react'
import { Settings, Server, Brain, Webhook, ExternalLink, ClipboardList, RefreshCw, CheckCircle2, AlertTriangle, Circle, Shield, Loader2, Eye, EyeOff, KeyRound, Trash2, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
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

        {/* Jenkins auto-setup (notification webhook + plugins) */}
        <JenkinsAutoSetup />

        {/* API Key Manager (multi-key, multi-provider) */}
        <ApiKeysManager />

        {/* LLM Configuration (provider + key + Test/Save) */}
        <LlmConfig />

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

interface LlmSettings {
  llm_provider: string
  anthropic_configured: boolean
  anthropic_key_preview: string
  anthropic_analysis_model: string
  anthropic_generation_model: string
  ollama_base_url: string
  analysis_model: string
  generation_model: string
}

// Locked dropdown options — typo-proof. Add new models here when Anthropic ships them.
const ANTHROPIC_MODELS: { id: string; label: string }[] = [
  { id: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (fast/cheap)' },
  { id: 'claude-sonnet-4-6',         label: 'Claude Sonnet 4.6 (balanced)' },
  { id: 'claude-opus-4-7',           label: 'Claude Opus 4.7 (most capable)' },
]

interface ApiKey {
  id: string
  name: string
  provider: string
  key_preview: string
  created_at: number
  active: boolean
}

const SUPPORTED_KEY_PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic' },
] as const

interface AutoSetupReport {
  ok: boolean
  webhook_url: string
  plugins_installed: string[]
  plugins_already_present: string[]
  jobs_configured: string[]
  jobs_already_configured: string[]
  errors: string[]
  restart_required: boolean
}

function JenkinsAutoSetup() {
  const [busy, setBusy] = useState(false)
  const [publicUrl, setPublicUrl] = useState('')
  const [report, setReport] = useState<AutoSetupReport | null>(null)
  const [error, setError] = useState('')

  async function run() {
    setBusy(true); setError(''); setReport(null)
    try {
      const r = await fetch('/api/jenkins/auto-setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ public_base_url: publicUrl.trim() }),
      })
      const data = await r.json()
      if (!r.ok) {
        setError(data.detail || `HTTP ${r.status}`)
        return
      }
      setReport(data)
    } catch (e: any) {
      setError(e?.message ?? 'Network error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-6 rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
          <Webhook className="h-4 w-4 text-accent" strokeWidth={1.75} />
        </div>
        <div>
          <p className="text-[14px] font-bold text-text-primary leading-none">Jenkins Webhook Setup</p>
          <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">Auto-install plugins + configure all jobs to push failures here</p>
        </div>
      </div>
      <div className="px-5 py-5 space-y-4">
        <div>
          <label className="block text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-1">Public webhook URL (optional)</label>
          <input
            type="text"
            placeholder={`Auto-detected if blank — e.g. http://your-app.example.com:8000`}
            value={publicUrl}
            onChange={e => setPublicUrl(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-accent-border/40 text-[12px] font-mono bg-white focus:outline-none focus:border-accent"
          />
          <p className="text-[10px] font-mono text-text-dim mt-1">URL that Jenkins should POST failure events to. Leave blank to derive from your browser URL.</p>
        </div>

        <Button
          size="sm"
          onClick={run}
          disabled={busy}
          className="gap-2 bg-accent hover:bg-accent-hi text-white text-[12px] h-9 px-4 font-mono rounded-lg"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Webhook className="h-3.5 w-3.5" strokeWidth={2} />}
          {busy ? 'Configuring Jenkins…' : 'Configure Jenkins for Webhooks'}
        </Button>

        {error && (
          <div className="rounded-lg border border-error/30 bg-error-dim px-3 py-2 text-[12px] font-mono text-error">{error}</div>
        )}

        {report && (
          <div className={cn(
            'rounded-lg border px-3 py-3 space-y-2 text-[12px] font-mono',
            report.ok ? 'border-success/30 bg-success-dim' : 'border-error/30 bg-error-dim',
          )}>
            <p className="flex items-center gap-2 font-semibold">
              {report.ok
                ? <CheckCircle2 className="h-4 w-4 text-success" strokeWidth={2} />
                : <AlertTriangle className="h-4 w-4 text-error" strokeWidth={2} />}
              {report.ok ? 'Setup complete' : 'Setup completed with errors'}
            </p>
            <p className="text-[11px] text-text-muted">Webhook URL: <code className="text-accent">{report.webhook_url}</code></p>
            {report.plugins_installed.length > 0 && (
              <p className="text-[11px]">Installed plugins: <span className="text-accent">{report.plugins_installed.join(', ')}</span></p>
            )}
            {report.plugins_already_present.length > 0 && (
              <p className="text-[11px] text-text-dim">Already installed: {report.plugins_already_present.join(', ')}</p>
            )}
            {report.jobs_configured.length > 0 && (
              <p className="text-[11px]">Configured jobs ({report.jobs_configured.length}): <span className="text-accent">{report.jobs_configured.join(', ')}</span></p>
            )}
            {report.jobs_already_configured.length > 0 && (
              <p className="text-[11px] text-text-dim">Already configured: {report.jobs_already_configured.join(', ')}</p>
            )}
            {report.errors.length > 0 && (
              <div className="text-[11px] text-error">
                <p className="font-semibold mb-1">Errors:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {report.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
            {report.restart_required && (
              <p className="text-[11px] text-warning flex items-start gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" strokeWidth={2} />
                <span>Plugins were installed — Jenkins must be restarted before notifications start firing. Manage Jenkins → Restart, or run <code>safeRestart</code>.</span>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ApiKeysManager() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [newName, setNewName] = useState('')
  const [newProvider, setNewProvider] = useState<string>('anthropic')
  const [newSecret, setNewSecret] = useState('')
  const [showSecret, setShowSecret] = useState(false)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState('')
  // Switch-then-delete flow: when user tries to delete the active key, prompt
  // them to pick a replacement from same-provider non-active keys first.
  const [switchPrompt, setSwitchPrompt] = useState<{ keyId: string; provider: string } | null>(null)
  const [pendingReplacement, setPendingReplacement] = useState<string>('')

  function refresh() {
    setLoading(true)
    fetch('/api/llm-keys')
      .then(r => r.json())
      .then(d => setKeys(d.keys || []))
      .catch(() => setKeys([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  async function handleAdd() {
    setError('')
    if (!newName.trim() || !newSecret.trim()) {
      setError('Name and key value are required.')
      return
    }
    setAdding(true)
    try {
      const r = await fetch('/api/llm-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName.trim(),
          provider: newProvider,
          key: newSecret.trim(),
        }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        setError(d.detail || `HTTP ${r.status}`)
        return
      }
      setNewName(''); setNewSecret(''); setShowSecret(false)
      refresh()
    } finally {
      setAdding(false)
    }
  }

  async function handleActivate(id: string) {
    setBusyId(id); setError('')
    try {
      const r = await fetch(`/api/llm-keys/${id}/activate`, { method: 'POST' })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        setError(d.detail || `HTTP ${r.status}`)
        return
      }
      refresh()
    } finally {
      setBusyId('')
    }
  }

  async function handleDelete(id: string) {
    const target = keys.find(k => k.id === id)
    if (!target) return
    if (target.active) {
      // Open switch-then-delete prompt (don't even call API; we'd just get 409)
      setSwitchPrompt({ keyId: id, provider: target.provider })
      setPendingReplacement('')
      return
    }
    setBusyId(id); setError('')
    try {
      const r = await fetch(`/api/llm-keys/${id}`, { method: 'DELETE' })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        setError(d.detail || `HTTP ${r.status}`)
        return
      }
      refresh()
    } finally {
      setBusyId('')
    }
  }

  async function confirmSwitchAndDelete() {
    if (!switchPrompt || !pendingReplacement) return
    setBusyId(switchPrompt.keyId); setError('')
    try {
      // 1. Activate replacement first
      const a = await fetch(`/api/llm-keys/${pendingReplacement}/activate`, { method: 'POST' })
      if (!a.ok) {
        setError(`Could not activate replacement (HTTP ${a.status})`)
        return
      }
      // 2. Now delete the previously-active key
      const d = await fetch(`/api/llm-keys/${switchPrompt.keyId}`, { method: 'DELETE' })
      if (!d.ok) {
        const body = await d.json().catch(() => ({}))
        setError(body.detail || `Delete failed HTTP ${d.status}`)
        return
      }
      setSwitchPrompt(null)
      setPendingReplacement('')
      refresh()
    } finally {
      setBusyId('')
    }
  }

  // Group keys by provider for sectioned rendering
  const grouped = keys.reduce<Record<string, ApiKey[]>>((acc, k) => {
    (acc[k.provider] ||= []).push(k)
    return acc
  }, {})

  return (
    <div className="mt-6 rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
          <KeyRound className="h-4 w-4 text-accent" strokeWidth={1.75} />
        </div>
        <div>
          <p className="text-[14px] font-bold text-text-primary leading-none">API Keys</p>
          <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">
            Manage multiple keys per provider. Active key feeds the LLM.
          </p>
        </div>
      </div>

      <div className="px-5 py-5 space-y-5">
        {/* Existing keys, grouped by provider */}
        {loading ? (
          <p className="text-[12px] font-mono text-text-dim">Loading…</p>
        ) : keys.length === 0 ? (
          <p className="text-[12px] font-mono text-text-dim">No keys yet. Add one below.</p>
        ) : (
          SUPPORTED_KEY_PROVIDERS.map(p => {
            const list = grouped[p.id]
            if (!list || list.length === 0) return null
            return (
              <div key={p.id}>
                <p className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-2">{p.label}</p>
                <div className="rounded-lg border border-accent-border/40 divide-y divide-accent-border/20">
                  {list.map(k => (
                    <div key={k.id} className="flex items-center gap-3 px-3 py-2.5">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[13px] font-semibold text-text-primary truncate">{k.name}</span>
                          {k.active && (
                            <span className="text-[9px] font-mono font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-success/15 text-success">
                              Active
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] font-mono text-text-muted mt-0.5">{k.key_preview}</p>
                      </div>
                      {!k.active && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-[11px] h-7 px-2.5 font-mono"
                          onClick={() => handleActivate(k.id)}
                          disabled={busyId === k.id}
                        >
                          {busyId === k.id ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Activate'}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-[11px] h-7 px-2 font-mono text-error hover:bg-error/10"
                        onClick={() => handleDelete(k.id)}
                        disabled={busyId === k.id}
                        aria-label={`Delete ${k.name}`}
                      >
                        <Trash2 className="h-3 w-3" strokeWidth={2} />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )
          })
        )}

        {/* Switch-then-delete confirm */}
        {switchPrompt && (
          <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 space-y-2">
            <div className="flex gap-2">
              <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" strokeWidth={2} />
              <p className="text-[11px] text-text-muted leading-relaxed">
                You're deleting the active key. Pick a replacement to activate first, then it'll be deleted.
              </p>
            </div>
            <Select
              size="sm"
              value={pendingReplacement}
              onChange={setPendingReplacement}
              placeholder="Choose replacement key…"
              options={keys
                .filter(k => k.provider === switchPrompt.provider && k.id !== switchPrompt.keyId)
                .map(k => ({ value: k.id, label: k.name, hint: k.key_preview }))}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                className="flex-1 text-[11px] h-7 font-mono border border-accent-border/40"
                onClick={() => { setSwitchPrompt(null); setPendingReplacement('') }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="flex-1 text-[11px] h-7 font-mono bg-error hover:bg-error/90 text-white"
                onClick={confirmSwitchAndDelete}
                disabled={!pendingReplacement || busyId !== ''}
              >
                {busyId ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Switch & Delete'}
              </Button>
            </div>
          </div>
        )}

        {/* Add new */}
        <div className="rounded-lg border border-accent-border/40 p-3 space-y-2.5">
          <p className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em]">Add Key</p>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Name (e.g. work, personal)"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              className="px-2.5 py-1.5 rounded-md border border-accent-border/40 text-[12px] font-mono bg-white focus:outline-none focus:border-accent"
            />
            <Select
              size="sm"
              value={newProvider}
              onChange={setNewProvider}
              options={SUPPORTED_KEY_PROVIDERS.map(p => ({ value: p.id, label: p.label }))}
            />
          </div>
          <div className="relative">
            <input
              type={showSecret ? 'text' : 'password'}
              placeholder={newProvider === 'anthropic' ? 'sk-ant-...' : 'API key'}
              value={newSecret}
              onChange={e => setNewSecret(e.target.value)}
              autoComplete="off"
              className="w-full px-2.5 py-1.5 pr-8 rounded-md border border-accent-border/40 text-[12px] font-mono bg-white focus:outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={() => setShowSecret(s => !s)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-text-dim hover:text-text-base"
              aria-label={showSecret ? 'Hide key' : 'Show key'}
            >
              {showSecret ? <EyeOff className="h-3 w-3" strokeWidth={2} /> : <Eye className="h-3 w-3" strokeWidth={2} />}
            </button>
          </div>
          {error && (
            <p className="text-[11px] font-mono text-error">{error}</p>
          )}
          <Button
            size="sm"
            className="w-full text-[11px] h-8 font-mono gap-1.5 bg-accent hover:bg-accent-hi text-white"
            onClick={handleAdd}
            disabled={adding || !newName.trim() || !newSecret.trim()}
          >
            {adding ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" strokeWidth={2.5} />}
            {adding ? 'Adding…' : 'Add Key'}
          </Button>
        </div>
      </div>
    </div>
  )
}

function modelOptions(currentValue: string): { id: string; label: string }[] {
  if (!currentValue || ANTHROPIC_MODELS.some(m => m.id === currentValue)) return ANTHROPIC_MODELS
  // Surface legacy/unknown saved value so user sees it explicitly instead of silent fallback
  return [...ANTHROPIC_MODELS, { id: currentValue, label: `${currentValue} (legacy)` }]
}

function LlmConfig() {
  const [loaded, setLoaded] = useState(false)
  const [provider, setProvider] = useState<'anthropic' | 'ollama'>('ollama')
  const [savedPreview, setSavedPreview] = useState('')
  const [keyInput, setKeyInput] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [analysisModel, setAnalysisModel] = useState('')
  const [generationModel, setGenerationModel] = useState('')
  const [ollamaUrl, setOllamaUrl] = useState('')
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null)
  const [savedToast, setSavedToast] = useState(false)

  function loadSettings() {
    fetch('/api/settings')
      .then(r => r.json())
      .then((d: LlmSettings) => {
        setProvider((d.llm_provider as 'anthropic' | 'ollama') || 'ollama')
        setSavedPreview(d.anthropic_key_preview || '')
        if (d.llm_provider === 'anthropic') {
          setAnalysisModel(d.anthropic_analysis_model || '')
          setGenerationModel(d.anthropic_generation_model || '')
        } else {
          setOllamaUrl(d.ollama_base_url || '')
          setAnalysisModel(d.analysis_model || '')
          setGenerationModel(d.generation_model || '')
        }
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }

  useEffect(() => { loadSettings() }, [])

  async function testConnection() {
    setTesting(true)
    setTestResult(null)
    const body: Record<string, string> = { provider }
    if (provider === 'anthropic' && keyInput.trim()) body.api_key = keyInput.trim()
    if (provider === 'ollama' && ollamaUrl.trim()) body.base_url = ollamaUrl.trim()
    try {
      const r = await fetch('/api/secrets/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      setTestResult({ ok: !!d.ok, detail: d.detail ?? '' })
    } catch (e: any) {
      setTestResult({ ok: false, detail: e?.message ?? 'Network error' })
    } finally {
      setTesting(false)
    }
  }

  async function save() {
    setSaving(true)
    const body: Record<string, string> = { provider }
    if (provider === 'anthropic') {
      if (keyInput.trim()) body.anthropic_api_key = keyInput.trim()
      // Always send dropdown selection (resolved value, falls back to default if blank)
      body.anthropic_analysis_model = analysisModel.trim() || ANTHROPIC_MODELS[0].id
      body.anthropic_generation_model = generationModel.trim() || ANTHROPIC_MODELS[1].id
    } else {
      if (ollamaUrl.trim()) body.ollama_base_url = ollamaUrl.trim()
      // Single Ollama model handles both analysis + generation
      const ollamaModel = analysisModel.trim()
      if (ollamaModel) {
        body.analysis_model = ollamaModel
        body.generation_model = ollamaModel
      }
    }
    try {
      const r = await fetch('/api/llm-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (r.ok) {
        setKeyInput('')  // clear input — server now has it
        setSavedToast(true)
        setTimeout(() => setSavedToast(false), 2500)
        loadSettings()  // refresh masked preview + provider
      } else {
        const d = await r.json().catch(() => ({}))
        setTestResult({ ok: false, detail: d.detail ?? `HTTP ${r.status}` })
      }
    } catch (e: any) {
      setTestResult({ ok: false, detail: e?.message ?? 'Network error' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-6 rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
          <Brain className="h-4 w-4 text-accent" strokeWidth={1.75} />
        </div>
        <div>
          <p className="text-[14px] font-bold text-text-primary leading-none">LLM Configuration</p>
          <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">Provider + API key (saved to .env, hot-reloaded)</p>
        </div>
      </div>

      <div className="px-5 py-5 space-y-5">
        {!loaded ? (
          <div className="text-[12px] font-mono text-text-dim">Loading…</div>
        ) : (
          <>
            {/* Provider radio */}
            <div>
              <label className="block text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-2">Provider</label>
              <div className="flex gap-2">
                {(['ollama', 'anthropic'] as const).map(p => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => { setProvider(p); setTestResult(null) }}
                    className={cn(
                      'flex-1 py-2 rounded-lg text-[12px] font-semibold border transition-all duration-150 cursor-pointer',
                      provider === p
                        ? 'bg-accent border-accent text-white'
                        : 'bg-white border-accent-border/40 text-text-base hover:bg-overlay/30'
                    )}
                  >
                    {p === 'anthropic' ? 'Anthropic (cloud)' : 'Ollama (local)'}
                  </button>
                ))}
              </div>
            </div>

            {/* Anthropic-specific fields */}
            {provider === 'anthropic' && (
              <>
                <div>
                  <label className="block text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-1">API Key</label>
                  {savedPreview && (
                    <p className="text-[11px] font-mono text-text-muted mb-1.5">
                      Saved: <code className="text-accent">{savedPreview}</code>
                    </p>
                  )}
                  <div className="relative">
                    <input
                      type={showKey ? 'text' : 'password'}
                      autoComplete="off"
                      placeholder={savedPreview ? 'Leave blank to keep saved key' : 'sk-ant-...'}
                      value={keyInput}
                      onChange={e => { setKeyInput(e.target.value); setTestResult(null) }}
                      className="w-full px-3 py-2 pr-10 rounded-lg border border-accent-border/40 text-[13px] font-mono bg-white focus:outline-none focus:border-accent"
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(s => !s)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-text-dim hover:text-text-base"
                      aria-label={showKey ? 'Hide key' : 'Show key'}
                    >
                      {showKey ? <EyeOff className="h-3.5 w-3.5" strokeWidth={2} /> : <Eye className="h-3.5 w-3.5" strokeWidth={2} />}
                    </button>
                  </div>
                  <p className="text-[10px] font-mono text-text-dim mt-1">Stored in .env. Never logged or returned by the API.</p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-1">Analysis Model</label>
                    <Select
                      value={analysisModel || ANTHROPIC_MODELS[0].id}
                      onChange={setAnalysisModel}
                      options={modelOptions(analysisModel).map(m => ({ value: m.id, label: m.label }))}
                    />
                    <p className="text-[10px] font-mono text-text-dim mt-1">Fast + cheap. Used for failure root-cause analysis.</p>
                  </div>
                  <div>
                    <label className="block text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-1">Generation Model</label>
                    <Select
                      value={generationModel || ANTHROPIC_MODELS[1].id}
                      onChange={setGenerationModel}
                      options={modelOptions(generationModel).map(m => ({ value: m.id, label: m.label }))}
                    />
                    <p className="text-[10px] font-mono text-text-dim mt-1">Higher quality. Used for pipeline generation.</p>
                  </div>
                </div>
              </>
            )}

            {/* Ollama-specific fields */}
            {provider === 'ollama' && (
              <>
                <div>
                  <label className="block text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-1">Ollama URL</label>
                  <input
                    type="text"
                    placeholder="http://localhost:11434"
                    value={ollamaUrl}
                    onChange={e => setOllamaUrl(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-accent-border/40 text-[12px] font-mono bg-white focus:outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-1">Model</label>
                  <input
                    type="text"
                    placeholder="llama3.1:8b"
                    value={analysisModel}
                    onChange={e => setAnalysisModel(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-accent-border/40 text-[12px] font-mono bg-white focus:outline-none focus:border-accent"
                  />
                  <p className="text-[10px] font-mono text-text-dim mt-1">Same model handles both analysis + generation.</p>
                </div>
              </>
            )}

            {/* Test result */}
            {testResult && (
              <div className={cn(
                'flex items-start gap-2 rounded-lg border px-3 py-2 text-[12px] font-mono',
                testResult.ok
                  ? 'border-success-border bg-success-dim text-success'
                  : 'border-error-border bg-error-dim text-error'
              )}>
                {testResult.ok
                  ? <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0" strokeWidth={2} />
                  : <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" strokeWidth={2} />}
                <span className="leading-relaxed">{testResult.detail}</span>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center gap-2 pt-1">
              <Button
                size="sm"
                variant="ghost"
                onClick={testConnection}
                disabled={testing || saving}
                className="gap-2 border border-accent-border/50 text-accent hover:bg-accent/5 text-[12px] h-9 px-4 font-mono rounded-lg"
              >
                {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />}
                {testing ? 'Testing…' : 'Test Connection'}
              </Button>
              <Button
                size="sm"
                onClick={save}
                disabled={saving || testing}
                className="gap-2 bg-accent hover:bg-accent-hi text-white font-semibold border-0 text-[12px] h-9 px-4 font-mono rounded-lg shadow-soft"
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Settings className="h-3.5 w-3.5" strokeWidth={2} />}
                {saving ? 'Saving…' : 'Save'}
              </Button>
              {savedToast && (
                <span className="text-[12px] font-mono text-success flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} /> Saved
                </span>
              )}
            </div>
          </>
        )}
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
