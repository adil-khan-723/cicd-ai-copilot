import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, KeyRound, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CredentialFields } from '@/types'

interface Props {
  open: boolean
  credentialId: string
  jobName: string
  index: number
  total: number
  onDone: (credentialId: string, credFields: CredentialFields | null) => void
  onSkipAll: () => void
}

type CredType = 'secret_text' | 'username_password' | 'ssh_key'

const TABS: { value: CredType; label: string }[] = [
  { value: 'secret_text',       label: 'Secret Text' },
  { value: 'username_password', label: 'User / Pass'  },
  { value: 'ssh_key',           label: 'SSH Key'      },
]

export function MissingCredentialModal({ open, credentialId, jobName, index, total, onDone, onSkipAll }: Props) {
  const [credType,    setCredType]    = useState<CredType>('secret_text')
  const [secretValue, setSecretValue] = useState('')
  const [username,    setUsername]    = useState('')
  const [password,    setPassword]    = useState('')
  const [sshUsername, setSshUsername] = useState('')
  const [privateKey,  setPrivateKey]  = useState('')

  useEffect(() => {
    if (open) {
      setCredType('secret_text')
      setSecretValue('')
      setUsername('')
      setPassword('')
      setSshUsername('')
      setPrivateKey('')
    }
  }, [open, credentialId])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onSkipAll() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onSkipAll])

  const filled =
    (credType === 'secret_text'       && secretValue.trim() !== '') ||
    (credType === 'username_password' && username.trim() !== '' && password.trim() !== '') ||
    (credType === 'ssh_key'           && sshUsername.trim() !== '' && privateKey.trim() !== '')

  function handleConfigure() {
    const fields: CredentialFields = {
      credential_type: credType,
      secret_value:    credType === 'secret_text'       ? secretValue  : undefined,
      username:        credType === 'username_password' ? username     : undefined,
      password:        credType === 'username_password' ? password     : undefined,
      ssh_username:    credType === 'ssh_key'           ? sshUsername  : undefined,
      private_key:     credType === 'ssh_key'           ? privateKey   : undefined,
    }
    onDone(credentialId, fields)
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-40 bg-[#1c1410]/40 backdrop-blur-[6px]"
            onClick={onSkipAll}
          />
          <motion.div
            key="modal"
            role="dialog" aria-modal="true"
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ type: 'spring', stiffness: 480, damping: 36 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
          >
            <div
              className="pointer-events-auto w-full max-w-[480px] rounded-2xl bg-white shadow-modal border border-[rgba(46,109,160,0.14)] overflow-hidden flex flex-col"
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-start gap-3.5 px-5 pt-5 pb-4 border-b border-[rgba(46,109,160,0.1)]">
                <div className="shrink-0 w-10 h-10 rounded-xl flex items-center justify-center bg-[rgba(46,109,160,0.06)] border border-[rgba(46,109,160,0.12)] text-[#2e6da0]">
                  <KeyRound className="h-5 w-5" strokeWidth={1.8} />
                </div>
                <div className="flex-1 min-w-0">
                  <h2 className="text-[15px] font-semibold text-text-primary leading-tight">
                    Create Missing Credential
                  </h2>
                  <p className="text-[12px] text-text-dim mt-0.5">
                    {index + 1} of {total} — required by <span className="font-mono font-semibold">{jobName}</span>
                  </p>
                </div>
                <button
                  onClick={onSkipAll}
                  className="shrink-0 text-text-dim hover:text-text-muted transition-colors rounded-lg p-1 hover:bg-overlay/60"
                  aria-label="Skip"
                >
                  <X className="h-4 w-4" strokeWidth={1.5} />
                </button>
              </div>

              {/* Body */}
              <div className="px-5 py-5 space-y-4 overflow-y-auto max-h-[60vh]">
                {/* Credential ID display */}
                <div className="rounded-xl border border-[rgba(46,109,160,0.12)] bg-[#f0f6fb] px-4 py-3">
                  <p className="text-[10px] font-mono text-text-dim uppercase tracking-[0.1em] mb-1">Credential ID</p>
                  <p className="text-[13px] font-mono font-semibold text-text-primary">{credentialId}</p>
                </div>

                {/* Type pill-tabs */}
                <div>
                  <p className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em] mb-2">
                    Credential Type
                  </p>
                  <div className="flex gap-2">
                    {TABS.map(tab => (
                      <button
                        key={tab.value}
                        onClick={() => setCredType(tab.value)}
                        className={cn(
                          'flex-1 py-1.5 rounded-lg border text-[11px] font-semibold transition-all duration-150 cursor-pointer',
                          credType === tab.value
                            ? 'border-[#2e6da0] bg-[#dbeafe] text-[#2e6da0]'
                            : 'border-[rgba(180,100,80,0.2)] text-text-dim hover:border-[#2e6da0]/40',
                        )}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Conditional fields */}
                {credType === 'secret_text' && (
                  <Field label="Secret Value">
                    <input
                      type="password"
                      placeholder="Paste secret value…"
                      value={secretValue}
                      onChange={e => setSecretValue(e.target.value)}
                      className="w-full h-9 rounded-lg border border-[rgba(46,109,160,0.2)] bg-white px-3 text-[13px] font-mono text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-[#2e6da0]/30 focus:border-[#2e6da0]/50 transition"
                    />
                  </Field>
                )}

                {credType === 'username_password' && (
                  <>
                    <Field label="Username">
                      <input
                        type="text"
                        placeholder="Username"
                        value={username}
                        onChange={e => setUsername(e.target.value)}
                        className="w-full h-9 rounded-lg border border-[rgba(46,109,160,0.2)] bg-white px-3 text-[13px] font-mono text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-[#2e6da0]/30 focus:border-[#2e6da0]/50 transition"
                      />
                    </Field>
                    <Field label="Password">
                      <input
                        type="password"
                        placeholder="Password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        className="w-full h-9 rounded-lg border border-[rgba(46,109,160,0.2)] bg-white px-3 text-[13px] font-mono text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-[#2e6da0]/30 focus:border-[#2e6da0]/50 transition"
                      />
                    </Field>
                  </>
                )}

                {credType === 'ssh_key' && (
                  <>
                    <Field label="SSH Username">
                      <input
                        type="text"
                        placeholder="git"
                        value={sshUsername}
                        onChange={e => setSshUsername(e.target.value)}
                        className="w-full h-9 rounded-lg border border-[rgba(46,109,160,0.2)] bg-white px-3 text-[13px] font-mono text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-[#2e6da0]/30 focus:border-[#2e6da0]/50 transition"
                      />
                    </Field>
                    <Field label="Private Key (PEM)">
                      <textarea
                        placeholder={'-----BEGIN OPENSSH PRIVATE KEY-----\n…\n-----END OPENSSH PRIVATE KEY-----'}
                        value={privateKey}
                        onChange={e => setPrivateKey(e.target.value)}
                        rows={4}
                        className="w-full rounded-lg border border-[rgba(46,109,160,0.2)] bg-white px-3 py-2 text-[12px] font-mono text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-[#2e6da0]/30 focus:border-[#2e6da0]/50 transition resize-y"
                      />
                    </Field>
                  </>
                )}

                <p className="text-[11px] text-text-dim italic">
                  Value goes direct to Jenkins — never stored or logged
                </p>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between gap-3 px-5 py-4 border-t border-[rgba(46,109,160,0.1)] bg-[#f9fbfd]">
                <button
                  onClick={() => onDone(credentialId, null)}
                  className="h-9 px-5 rounded-xl text-[13px] font-semibold font-sans border border-[rgba(46,109,160,0.18)] text-text-muted bg-white hover:bg-overlay/60 hover:text-text-base transition-all duration-150 cursor-pointer"
                >
                  Skip this one
                </button>
                <button
                  onClick={handleConfigure}
                  disabled={!filled}
                  className={cn(
                    'h-9 px-6 rounded-xl text-[13px] font-bold font-sans flex items-center gap-2 text-white transition-all duration-150 cursor-pointer active:scale-[0.98]',
                    filled ? 'bg-[#2e6da0] hover:bg-[#265d8c]' : 'bg-[#2e6da0]/40 cursor-not-allowed',
                  )}
                  title={!filled ? 'Fill in all required fields first' : undefined}
                >
                  Create & Next <ChevronRight className="h-3.5 w-3.5" strokeWidth={2.5} />
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-mono font-semibold text-text-dim uppercase tracking-[0.1em]">{label}</p>
      {children}
    </div>
  )
}
