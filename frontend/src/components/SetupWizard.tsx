import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Info, Loader2, CheckCircle2, Server, XCircle } from 'lucide-react'
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
    jenkins_url:   initialData?.jenkins_url   ?? '',
    jenkins_user:  initialData?.jenkins_user  ?? '',
    jenkins_token: initialData?.jenkins_token ?? '',
  })
  const [error,            setError]            = useState('')
  const [loading,          setLoading]          = useState(false)
  const [saved,            setSaved]            = useState(false)
  const [jenkinsTestState, setJenkinsTestState] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [jenkinsTestDetail, setJenkinsTestDetail] = useState('')

  async function testJenkins() {
    if (!form.jenkins_url.trim()) return
    setJenkinsTestState('testing')
    setJenkinsTestDetail('')
    try {
      const r = await fetch('/api/secrets/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: 'jenkins' }),
      })
      const data = await r.json()
      setJenkinsTestState(data?.ok ? 'ok' : 'fail')
      if (!data?.ok && data?.detail) setJenkinsTestDetail(data.detail)
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
    setLoading(true); setError('')
    try {
      const res = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const body = await res.json()
        setError(body.detail ?? 'Setup failed'); return
      }
      setSaved(true)
      localStorage.setItem('devops_ai_configured', '1')
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
                  <h2 className="text-sm font-semibold text-text-primary">Project Setup</h2>
                  <p className="text-[11px] text-text-muted mt-0.5">Connect Jenkins</p>
                </div>
              </div>

              <div className="space-y-5">
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
                      onBlur={testJenkins}
                    />
                    {jenkinsTestState !== 'idle' && (
                      <div className="flex items-center gap-1.5 mt-1.5">
                        {jenkinsTestState === 'testing' && <Loader2 className="h-3 w-3 text-text-dim animate-spin" />}
                        {jenkinsTestState === 'ok'      && <CheckCircle2 className="h-3 w-3 text-success" strokeWidth={2} />}
                        {jenkinsTestState === 'fail'    && <XCircle className="h-3 w-3 text-error" strokeWidth={2} />}
                        <span className={`text-[10px] font-mono ${jenkinsTestState === 'ok' ? 'text-success' : jenkinsTestState === 'fail' ? 'text-error' : 'text-text-dim'}`}>
                          {jenkinsTestState === 'testing'
                            ? 'Connecting…'
                            : jenkinsTestState === 'ok'
                            ? 'Connected'
                            : jenkinsTestDetail || 'Cannot reach Jenkins'}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="Username"
                      placeholder="admin"
                      value={form.jenkins_user}
                      onChange={set('jenkins_user')}
                    />
                    <Input
                      label="API Token"
                      type="password"
                      placeholder="••••••••"
                      value={form.jenkins_token}
                      onChange={set('jenkins_token')}
                    />
                  </div>

                  {/* Hint */}
                  <div className="flex gap-2.5 rounded-lg border border-info/15 bg-info-dim p-3">
                    <Info className="h-3.5 w-3.5 text-info shrink-0 mt-0.5" />
                    <p className="text-[11px] text-text-muted leading-relaxed">
                      The <span className="text-text-primary font-medium">API Token</span> is not
                      your Jenkins password. Get one at{' '}
                      <em className="not-italic text-info">
                        Jenkins → User → Configure → API Token → Add new Token
                      </em>.
                    </p>
                  </div>
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
