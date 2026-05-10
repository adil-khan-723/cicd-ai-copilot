import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Info, Loader2, CheckCircle2, Server, XCircle, Brain } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { SetupFormData } from '@/types'

interface SetupWizardProps {
  visible:      boolean
  initialData?: Partial<SetupFormData>
  onClose:      () => void
  onSaved:      (repo: string) => void
}

export function SetupWizard({ visible, initialData, onClose, onSaved }: SetupWizardProps) {
  const [form, setForm] = useState<SetupFormData>({
    alias:               initialData?.alias               ?? '',
    jenkins_url:         initialData?.jenkins_url         ?? '',
    jenkins_user:        initialData?.jenkins_user        ?? '',
    jenkins_token:       initialData?.jenkins_token       ?? '',
    jenkins_auth_method: initialData?.jenkins_auth_method ?? 'token',
  })
  const [error,             setError]             = useState('')
  const [loading,           setLoading]           = useState(false)
  const [saved,             setSaved]             = useState(false)
  const [jenkinsTestState,  setJenkinsTestState]  = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [jenkinsTestDetail, setJenkinsTestDetail] = useState('')
  // LLM step (optional in wizard; full UI lives in Settings)
  const [llmProvider, setLlmProvider] = useState<'ollama' | 'anthropic'>('ollama')
  const [llmKey, setLlmKey] = useState('')
  const [llmTestState, setLlmTestState] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [llmTestDetail, setLlmTestDetail] = useState('')

  async function testLlm() {
    setLlmTestState('testing')
    setLlmTestDetail('')
    const body: Record<string, string> = { provider: llmProvider }
    if (llmProvider === 'anthropic' && llmKey.trim()) body.api_key = llmKey.trim()
    try {
      const r = await fetch('/api/secrets/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      setLlmTestState(d?.ok ? 'ok' : 'fail')
      if (!d?.ok && d?.detail) setLlmTestDetail(d.detail)
    } catch {
      setLlmTestState('fail')
      setLlmTestDetail('Network error')
    }
  }

  async function testJenkins() {
    if (!form.jenkins_url.trim() || !form.jenkins_token.trim()) return
    setJenkinsTestState('testing')
    setJenkinsTestDetail('')
    try {
      const r = await fetch('/api/secrets/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: 'jenkins',
          jenkins_url: form.jenkins_url.trim(),
          jenkins_user: form.jenkins_user.trim(),
          jenkins_token: form.jenkins_token.trim(),
          jenkins_auth_method: form.jenkins_auth_method,
        }),
      })
      const data = await r.json()
      setJenkinsTestState(data?.ok ? 'ok' : 'fail')
      if (!data?.ok && data?.detail) setJenkinsTestDetail(data.detail)
      else if (data?.ok && data?.detail) setJenkinsTestDetail(data.detail)
    } catch {
      setJenkinsTestState('fail')
      setJenkinsTestDetail('Network error')
    }
  }

  function set(key: keyof SetupFormData) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm(f => ({ ...f, [key]: e.target.value }))
      setError('')
    }
  }

  async function handleSave() {
    if (!form.alias.trim()) { setError('Profile name is required'); return }
    setLoading(true); setError('')
    try {
      const res = await fetch('/api/profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const body = await res.json()
        setError(body.detail ?? 'Setup failed'); return
      }
      // activate the new profile
      const { profile } = await res.json()
      await fetch(`/api/profiles/${profile.id}/activate`, { method: 'POST' })

      // If user provided LLM config, persist it (skipped silently when blank)
      const wantSaveLlm = llmProvider === 'anthropic' ? llmKey.trim().length > 0 : true
      if (wantSaveLlm) {
        const llmBody: Record<string, string> = { provider: llmProvider }
        if (llmProvider === 'anthropic' && llmKey.trim()) llmBody.anthropic_api_key = llmKey.trim()
        try {
          await fetch('/api/llm-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(llmBody),
          })
        } catch { /* non-fatal — user can fix in Settings later */ }
      }

      setSaved(true)
      setTimeout(() => { onSaved(''); setSaved(false) }, 700)
    } catch {
      setError('Network error — is the server running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(3,7,18,0.85)', backdropFilter: 'blur(8px)' }}
        >
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="w-full max-w-md rounded-xl border border-glass-hi bg-card shadow-modal overflow-hidden"
          >
            {/* Gradient top bar */}
            <div className="h-px w-full bg-gradient-accent opacity-60" />

            <div className="p-6">
              {/* Header */}
              <div className="flex items-center gap-3 mb-6">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-accent shadow-glow-accent">
                  <Zap className="h-4 w-4 text-white" strokeWidth={2.5} />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-text-primary">Add Jenkins Account</h2>
                  <p className="text-[11px] text-text-muted mt-0.5">Connect a Jenkins instance</p>
                </div>
              </div>

              <div className="space-y-5">
                {/* Profile name */}
                <Input
                  label="Profile name"
                  placeholder="e.g. Production, Staging, Client A"
                  value={form.alias}
                  onChange={set('alias')}
                />

                {/* Jenkins */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Server className="h-3.5 w-3.5 text-text-dim" />
                    <span className="text-[10px] font-semibold text-text-muted uppercase tracking-widest">Jenkins</span>
                  </div>
                  <div>
                    <Input
                      label="URL"
                      placeholder="https://jenkins.example.com"
                      value={form.jenkins_url}
                      onChange={e => { set('jenkins_url')(e); setJenkinsTestState('idle') }}
                    />
                  </div>
                  {/* Auth method radio */}
                  <div>
                    <span className="text-[10px] font-semibold text-text-muted uppercase tracking-widest mb-1.5 block">Auth method</span>
                    <div className="flex gap-2">
                      {(['token', 'password'] as const).map(m => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => setForm(f => ({ ...f, jenkins_auth_method: m }))}
                          className={`flex-1 py-1.5 rounded-md text-[11px] font-semibold border transition-all duration-150 cursor-pointer ${
                            form.jenkins_auth_method === m
                              ? 'bg-accent border-accent text-white'
                              : 'bg-white border-accent-border/40 text-text-base hover:bg-overlay/30'
                          }`}
                        >
                          {m === 'token' ? 'API Token (recommended)' : 'Password'}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="Username"
                      placeholder="admin"
                      value={form.jenkins_user}
                      onChange={e => { set('jenkins_user')(e); setJenkinsTestState('idle') }}
                    />
                    <Input
                      label={form.jenkins_auth_method === 'password' ? 'Password' : 'API Token'}
                      type="password"
                      placeholder="••••••••"
                      value={form.jenkins_token}
                      onChange={e => { set('jenkins_token')(e); setJenkinsTestState('idle') }}
                    />
                  </div>

                  {/* Test connection */}
                  <div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={testJenkins}
                      disabled={jenkinsTestState === 'testing' || !form.jenkins_url.trim() || !form.jenkins_token.trim()}
                    >
                      {jenkinsTestState === 'testing' ? (
                        <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Testing…</>
                      ) : (
                        'Test Connection'
                      )}
                    </Button>
                    {jenkinsTestState !== 'idle' && jenkinsTestState !== 'testing' && (
                      <div className="flex items-start gap-1.5 mt-2">
                        {jenkinsTestState === 'ok'   && <CheckCircle2 className="h-3 w-3 text-success shrink-0 mt-0.5" strokeWidth={2} />}
                        {jenkinsTestState === 'fail' && <XCircle className="h-3 w-3 text-error shrink-0 mt-0.5" strokeWidth={2} />}
                        <span className={`text-[10px] font-mono leading-relaxed ${jenkinsTestState === 'ok' ? 'text-success' : 'text-error'}`}>
                          {jenkinsTestState === 'ok'
                            ? (jenkinsTestDetail || 'Connected')
                            : (jenkinsTestDetail || 'Cannot reach Jenkins')}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Hint */}
                  <div className="flex gap-2.5 rounded-lg border border-info/15 bg-info-dim p-3">
                    <Info className="h-3.5 w-3.5 text-info shrink-0 mt-0.5" />
                    <p className="text-[11px] text-text-muted leading-relaxed">
                      {form.jenkins_auth_method === 'password' ? (
                        <>
                          Using your Jenkins login <span className="text-text-primary font-medium">password</span>.
                          Works for all features but <span className="text-warning">not recommended</span> —
                          API tokens are revocable per-integration and survive 2FA / SSO.
                        </>
                      ) : (
                        <>
                          The <span className="text-text-primary font-medium">API Token</span> is not your
                          Jenkins password. Get one at{' '}
                          <em className="not-italic text-info">
                            [Your name] (top-right) → Security → API Token → Add new Token → Generate
                          </em>.
                        </>
                      )}
                    </p>
                  </div>
                </div>

                {/* LLM (optional in wizard, full config in Settings) */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Brain className="h-3.5 w-3.5 text-text-dim" />
                    <span className="text-[10px] font-semibold text-text-muted uppercase tracking-widest">LLM (optional)</span>
                  </div>
                  <div className="flex gap-2">
                    {(['ollama', 'anthropic'] as const).map(p => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => { setLlmProvider(p); setLlmTestState('idle') }}
                        className={`flex-1 py-1.5 rounded-md text-[11px] font-semibold border transition-all duration-150 cursor-pointer ${
                          llmProvider === p
                            ? 'bg-accent border-accent text-white'
                            : 'bg-white border-accent-border/40 text-text-base hover:bg-overlay/30'
                        }`}
                      >
                        {p === 'anthropic' ? 'Anthropic (cloud)' : 'Ollama (local)'}
                      </button>
                    ))}
                  </div>
                  {llmProvider === 'anthropic' && (
                    <div>
                      <Input
                        label="Anthropic API Key"
                        type="password"
                        placeholder="sk-ant-..."
                        value={llmKey}
                        onChange={e => { setLlmKey(e.target.value); setLlmTestState('idle') }}
                        onBlur={() => llmKey.trim() && testLlm()}
                      />
                      {llmTestState !== 'idle' && (
                        <div className="flex items-center gap-1.5 mt-1.5">
                          {llmTestState === 'testing' && <Loader2 className="h-3 w-3 text-text-dim animate-spin" />}
                          {llmTestState === 'ok'      && <CheckCircle2 className="h-3 w-3 text-success" strokeWidth={2} />}
                          {llmTestState === 'fail'    && <XCircle className="h-3 w-3 text-error" strokeWidth={2} />}
                          <span className={`text-[10px] font-mono ${llmTestState === 'ok' ? 'text-success' : llmTestState === 'fail' ? 'text-error' : 'text-text-dim'}`}>
                            {llmTestState === 'testing'
                              ? 'Testing key…'
                              : llmTestState === 'ok'
                              ? 'Key valid'
                              : llmTestDetail || 'Key rejected'}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                  <p className="text-[10px] text-text-dim">
                    You can change this anytime in Settings → LLM Configuration.
                  </p>
                </div>

                {error && (
                  <div className="rounded-lg border border-error/20 bg-error-dim px-3 py-2">
                    <p className="text-[11px] text-error">{error}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 pt-1">
                  <Button variant="outline" size="sm" className="flex-1" onClick={onClose} disabled={loading}>
                    Skip for now
                  </Button>
                  <Button size="sm" className="flex-1" onClick={handleSave} disabled={loading || saved}>
                    {loading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : saved ? (
                      <><CheckCircle2 className="h-3.5 w-3.5" /> Saved</>
                    ) : (
                      'Save & Connect'
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
