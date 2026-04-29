import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Loader2, Trash2, Pencil, Check } from 'lucide-react'
import { DottedSurface } from '@/components/ui/dotted-surface'
import { ThemeToggle } from '@/components/ThemeToggle'
import type { Theme } from '@/hooks/useTheme'

interface Profile {
  id: string
  alias: string
  jenkins_url: string
  jenkins_user: string
  active: boolean
}

interface ProfilePickerProps {
  onSelect:    (profileId: string) => void
  onAddNew:    () => void
  theme:       Theme
  toggleTheme: () => void
}

function initials(alias: string): string {
  return alias
    .split(/\s+/)
    .map(w => w[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('')
}

function hostFromUrl(url: string): string {
  try { return new URL(url).host } catch { return url }
}

// Gradient pairs: [from, to]
const AVATAR_GRADIENTS: [string, string][] = [
  ['#7c3aed', '#a855f7'],
  ['#2563eb', '#3b82f6'],
  ['#059669', '#10b981'],
  ['#ea580c', '#f97316'],
  ['#e11d48', '#f43f5e'],
  ['#0891b2', '#06b6d4'],
]

function avatarGradient(id: string): [string, string] {
  let hash = 0
  for (const c of id) hash = (hash * 31 + c.charCodeAt(0)) & 0xffff
  return AVATAR_GRADIENTS[hash % AVATAR_GRADIENTS.length]
}


export function ProfilePicker({ onSelect, onAddNew, theme, toggleTheme }: ProfilePickerProps) {
  const [profiles,   setProfiles]   = useState<Profile[]>([])
  const [loading,    setLoading]    = useState(true)
  const [activating, setActivating] = useState<string | null>(null)
  const [deleting,   setDeleting]   = useState<string | null>(null)
  const [editingId,  setEditingId]  = useState<string | null>(null)
  const [editAlias,  setEditAlias]  = useState('')

  async function load() {
    try {
      const r = await fetch('/api/profiles')
      const d = await r.json()
      setProfiles(d.profiles ?? [])
    } catch {
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleSelect(profile: Profile) {
    setActivating(profile.id)
    try {
      await fetch(`/api/profiles/${profile.id}/activate`, { method: 'POST' })
      onSelect(profile.id)
    } finally {
      setActivating(null)
    }
  }

  async function handleDelete(e: React.MouseEvent, profile: Profile) {
    e.stopPropagation()
    setDeleting(profile.id)
    try {
      await fetch(`/api/profiles/${profile.id}`, { method: 'DELETE' })
      await load()
    } finally {
      setDeleting(null)
    }
  }

  async function handleRename(e: React.MouseEvent, profile: Profile) {
    e.stopPropagation()
    setEditingId(profile.id)
    setEditAlias(profile.alias)
  }

  async function commitRename(profile: Profile) {
    if (!editAlias.trim()) return
    await fetch(`/api/profiles/${profile.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alias: editAlias }),
    })
    setEditingId(null)
    await load()
  }

  const isDark = theme === 'dark'

  return (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{ background: 'var(--c-bg)', transition: 'background 0.45s ease' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Three.js dotted wave surface */}
      <DottedSurface style={{ zIndex: 1 }} />

      {/* Header */}
      <motion.div
        className="mb-16 text-center relative z-10"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1
          className="leading-none"
          style={{
            fontSize: 'clamp(3rem, 6vw, 5rem)',
            fontWeight: 300,
            letterSpacing: '-0.04em',
            color: 'var(--c-text-primary)',
            transition: 'color 0.45s ease',
          }}
        >
          Who's connecting?
        </h1>
        <p
          style={{
            fontSize: 'clamp(1rem, 1.8vw, 1.2rem)',
            fontWeight: 300,
            fontFamily: 'ui-monospace, monospace',
            letterSpacing: '0.08em',
            opacity: 0.6,
            color: 'var(--c-text-muted)',
            marginTop: '1rem',
            transition: 'color 0.45s ease',
          }}
        >
          select a jenkins account to continue
        </p>
      </motion.div>

      {loading ? (
        <Loader2 style={{ color: '#c9706a' }} className="h-7 w-7 animate-spin" />
      ) : (
        <motion.div
          className="relative z-10 flex flex-wrap gap-8 justify-center px-8"
          style={{ maxWidth: '72rem' }}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12, duration: 0.35, ease: 'easeOut' }}
        >
          <AnimatePresence>
            {profiles.map((profile, i) => {
              const [from, to] = avatarGradient(profile.id)
              return (
                <motion.div
                  key={profile.id}
                  layout
                  initial={{ opacity: 0, scale: 0.88, y: 10 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.82 }}
                  transition={{ type: 'spring', stiffness: 380, damping: 26, delay: i * 0.06 }}
                  onClick={() => handleSelect(profile)}
                  className="group relative flex flex-col items-center gap-4 cursor-pointer select-none"
                  style={{ width: '9rem' }}
                >
                  {/* Avatar */}
                  <div className="relative">
                    {/* Glow ring on hover */}
                    <div
                      className="absolute inset-0 rounded-[28px] opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-md scale-110"
                      style={{ background: `linear-gradient(135deg, ${from}, ${to})` }}
                    />
                    <div
                      className="relative flex items-center justify-center rounded-[28px] text-white transition-transform duration-200 group-hover:scale-[1.07]"
                      style={{
                        width: '88px',
                        height: '88px',
                        fontSize: '1.7rem',
                        fontWeight: 700,
                        letterSpacing: '-0.02em',
                        background: `linear-gradient(145deg, ${from} 0%, ${to} 100%)`,
                        boxShadow: `0 4px 6px rgba(0,0,0,0.3), 0 12px 28px ${from}70, inset 0 1px 0 rgba(255,255,255,0.25)`,
                        border: `1px solid rgba(255,255,255,0.15)`,
                      }}
                    >
                      {/* inner shine */}
                      <div className="absolute inset-0 rounded-[28px] pointer-events-none"
                        style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.18) 0%, transparent 55%)' }}
                      />
                      {activating === profile.id
                        ? <Loader2 className="h-8 w-8 animate-spin relative z-10" />
                        : <span className="relative z-10">{initials(profile.alias)}</span>
                      }
                    </div>

                    {/* Action buttons on hover */}
                    <div className="absolute -top-2 -right-2 hidden group-hover:flex gap-1 z-10">
                      <button
                        onClick={e => handleRename(e, profile)}
                        className="h-6 w-6 rounded-full flex items-center justify-center transition-colors shadow-sm"
                        style={{
                          background: 'var(--c-card)',
                          border: '1px solid var(--c-accent-border)',
                        }}
                        title="Rename"
                      >
                        <Pencil className="h-3 w-3" style={{ color: 'var(--c-text-muted)' }} />
                      </button>
                      <button
                        onClick={e => handleDelete(e, profile)}
                        className="h-6 w-6 rounded-full flex items-center justify-center transition-colors shadow-sm"
                        style={{
                          background: 'var(--c-card)',
                          border: `1px solid ${isDark ? 'rgba(224,85,69,0.3)' : 'rgba(184,60,46,0.3)'}`,
                        }}
                        title="Delete"
                      >
                        {deleting === profile.id
                          ? <Loader2 className="h-3 w-3 animate-spin" style={{ color: 'var(--c-error)' }} />
                          : <Trash2 className="h-3 w-3" style={{ color: 'var(--c-error)' }} />
                        }
                      </button>
                    </div>
                  </div>

                  {/* Label */}
                  {editingId === profile.id ? (
                    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                      <input
                        autoFocus
                        value={editAlias}
                        onChange={e => setEditAlias(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') commitRename(profile)
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        className="w-24 text-center text-[12px] font-mono rounded-md px-1.5 py-0.5 outline-none"
                        style={{
                          background: 'var(--c-overlay)',
                          border: '1px solid var(--c-accent-border)',
                          color: 'var(--c-text-primary)',
                        }}
                      />
                      <button onClick={() => commitRename(profile)} style={{ color: 'var(--c-success)' }} className="hover:opacity-80">
                        <Check className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ) : (
                    <div className="text-center">
                      <p
                        className="leading-tight transition-colors group-hover:opacity-80"
                        style={{ fontSize: '0.95rem', fontWeight: 400, color: 'var(--c-text-primary)' }}
                      >
                        {profile.alias}
                      </p>
                      <p
                        className="font-mono truncate max-w-[8rem] mt-1.5"
                        style={{ fontSize: '12px', fontWeight: 500, color: 'var(--c-text-base)' }}
                      >
                        {profile.jenkins_user}
                      </p>
                      <p
                        className="font-mono truncate max-w-[8rem]"
                        style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}
                      >
                        {hostFromUrl(profile.jenkins_url)}
                      </p>
                    </div>
                  )}
                </motion.div>
              )
            })}
          </AnimatePresence>

          {/* Add new account card */}
          <motion.div
            layout
            onClick={onAddNew}
            initial={{ opacity: 0, scale: 0.88 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 380, damping: 26, delay: profiles.length * 0.06 }}
            className="flex flex-col items-center gap-4 cursor-pointer select-none group"
            style={{ width: '9rem' }}
          >
            <div
              className="flex items-center justify-center rounded-[28px] border-2 border-dashed transition-all duration-200 group-hover:scale-[1.07]"
              style={{
                width: '88px',
                height: '88px',
                borderColor: 'var(--c-accent-border)',
                color: 'var(--c-text-muted)',
              }}
            >
              <Plus className="h-8 w-8" strokeWidth={1.5} />
            </div>
            <p style={{ fontSize: '0.95rem', fontWeight: 400, color: 'var(--c-text-muted)' }}>
              Add account
            </p>
          </motion.div>
        </motion.div>
      )}

      {/* Theme toggle — centered below cards */}
      <motion.div
        className="relative z-10 mt-12 flex flex-col items-center gap-2"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4, ease: 'easeOut' }}
      >
        <ThemeToggle theme={theme} toggle={toggleTheme} size="md" />
        <span
          className="font-mono"
          style={{ fontSize: '11px', color: 'var(--c-text-dim)', opacity: 0.55 }}
        >
          {theme === 'dark' ? 'dark mode' : 'light mode'}
        </span>
      </motion.div>
    </motion.div>
  )
}
