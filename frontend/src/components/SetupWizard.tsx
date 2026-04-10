import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Info, Loader2, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { SetupFormData } from '@/types'

interface SetupWizardProps {
  visible: boolean
  initialData?: Partial<SetupFormData>
  onClose: () => void
  onSaved: (repo: string) => void
}

export function SetupWizard({ visible, initialData, onClose, onSaved }: SetupWizardProps) {
  const [form, setForm] = useState<SetupFormData>({
    github_repo: initialData?.github_repo ?? '',
    github_token: initialData?.github_token ?? '',
    jenkins_url: initialData?.jenkins_url ?? '',
    jenkins_user: initialData?.jenkins_user ?? '',
    jenkins_token: initialData?.jenkins_token ?? '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)

  function set(key: keyof SetupFormData) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((f) => ({ ...f, [key]: e.target.value }))
      setError('')
    }
  }

  async function handleSave() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const body = await res.json()
        setError(body.detail ?? 'Setup failed')
        return
      }
      setSaved(true)
      localStorage.setItem('devops_ai_configured', '1')
      localStorage.setItem('devops_ai_repo', form.github_repo)
      setTimeout(() => {
        onSaved(form.github_repo)
        setSaved(false)
      }, 800)
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center gap-2 mb-6">
              <div className="flex h-7 w-7 items-center justify-center rounded bg-white/5 border border-border">
                <Zap className="h-3.5 w-3.5 text-white/60" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-text-primary">Project Setup</h2>
                <p className="text-xs text-text-muted">Connect GitHub and Jenkins</p>
              </div>
            </div>

            <div className="flex flex-col gap-4">
              {/* GitHub */}
              <div className="space-y-3">
                <p className="text-xs font-medium text-text-dim uppercase tracking-wider">GitHub</p>
                <Input
                  label="Repository"
                  placeholder="owner/repo"
                  value={form.github_repo}
                  onChange={set('github_repo')}
                />
                <Input
                  label="Personal Access Token"
                  type="password"
                  placeholder="ghp_... or github_pat_..."
                  value={form.github_token}
                  onChange={set('github_token')}
                />
              </div>

              {/* Divider */}
              <div className="border-t border-border-subtle" />

              {/* Jenkins */}
              <div className="space-y-3">
                <p className="text-xs font-medium text-text-dim uppercase tracking-wider">Jenkins</p>
                <Input
                  label="URL"
                  placeholder="https://jenkins.example.com"
                  value={form.jenkins_url}
                  onChange={set('jenkins_url')}
                />
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

                {/* Hint box */}
                <div className="flex gap-2 rounded border border-border-subtle bg-surface p-3">
                  <Info className="h-3.5 w-3.5 text-info shrink-0 mt-0.5" />
                  <p className="text-xs text-text-muted leading-relaxed">
                    The <strong className="text-text-primary">API Token</strong> is not your Jenkins
                    password. Get one at <em>Jenkins → User → Configure → API Token → Add new
                    Token</em>.
                  </p>
                </div>
              </div>

              {error && (
                <p className="text-xs text-error rounded border border-error/20 bg-error/5 px-3 py-2">
                  {error}
                </p>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={onClose}
                  disabled={loading}
                >
                  Skip for now
                </Button>
                <Button
                  size="sm"
                  className="flex-1"
                  onClick={handleSave}
                  disabled={loading || saved}
                >
                  {loading ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : saved ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                  ) : (
                    'Save & Connect'
                  )}
                </Button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
