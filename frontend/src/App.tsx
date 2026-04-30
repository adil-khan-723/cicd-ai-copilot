import { useState, useCallback, useEffect, useRef } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { useChatStore } from '@/hooks/useChatStore'
import { motion, AnimatePresence } from 'framer-motion'
import { Sidebar } from '@/components/Sidebar'
import { Topbar } from '@/components/Topbar'
import { SetupWizard } from '@/components/SetupWizard'
import { ProfilePicker } from '@/components/ProfilePicker'
import { PipelineFeed } from '@/components/PipelineFeed'
import { ChatPanel } from '@/components/ChatPanel'
import { JobsBrowser } from '@/components/JobsBrowser'
import { SettingsPanel } from '@/components/SettingsPanel'
import { BuildDetailDrawer } from '@/components/BuildDetailDrawer'
import { useEventStream } from '@/hooks/useEventStream'
import type { ActivePanel, BuildCard, SSEEvent } from '@/types'

function makeKey(job: string, build: string | number) {
  return `${job}_${build}`
}

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme()
  const [activePanel,    setActivePanel]    = useState<ActivePanel>('pipeline')
  const [setupVisible,   setSetupVisible]   = useState(false)
  const [isConfigured,   setIsConfigured]   = useState(true)
  const [profilePicking, setProfilePicking] = useState(false)
  const [repoName,      setRepoName]      = useState('')
  const [jenkinsStatus, setJenkinsStatus] = useState<'connected' | 'disconnected' | 'unknown'>('unknown')
  const [cards,         setCards]         = useState<Map<string, BuildCard>>(() => {
    try {
      const raw = localStorage.getItem('pipeline_feed_cards')
      if (raw) return new Map(JSON.parse(raw) as [string, BuildCard][])
    } catch { /* corrupt storage — start fresh */ }
    return new Map()
  })
  const [bootDone,      setBootDone]      = useState(false)

  // ── Chat state — multi-session store keyed per profile ───────────────────
  const [activeProfileId, setActiveProfileId] = useState<string>('')
  const chatStore = useChatStore(activeProfileId)
  const [chatStreaming, setChatStreaming] = useState(false)

  // ── Jobs wire-up state lifted so it survives panel switches ───────────────
  const [wireStatus, setWireStatus] = useState<Record<string, 'ok' | 'already' | 'err'>>({})
  const [selectedCard, setSelectedCard] = useState<BuildCard | null>(null)
  const [selectedStage, setSelectedStage] = useState<string | null>(null)

  // ── Known Jenkins job names — used to filter phantom cards ────────────────
  const [knownJobs, setKnownJobs] = useState<Set<string>>(new Set())

  function handleWireStatus(name: string, status: 'ok' | 'already' | 'err') {
    setWireStatus(prev => ({ ...prev, [name]: status }))
  }

  // Real liveness check — hits /api/health with 6s abort so UI reflects truth fast
  function checkJenkinsLiveness() {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 6000)
    fetch('/api/health', { signal: ctrl.signal, cache: 'no-store' })
      .then(r => r.json())
      .then(data => setJenkinsStatus(data?.ok ? 'connected' : 'disconnected'))
      .catch(() => setJenkinsStatus('disconnected'))
      .finally(() => clearTimeout(timer))
  }

  // Bootstrap: fetch server settings on load
  useEffect(() => {
    fetch('/api/profiles')
      .then(r => r.json())
      .then(data => {
        const profiles = data.profiles ?? []
        if (profiles.length === 0) {
          // No profiles yet — go straight to setup wizard
          setIsConfigured(false)
          setSetupVisible(true)
        } else {
          // Always show profile picker on load
          setProfilePicking(true)
        }
      })
      .catch(() => {
        setIsConfigured(false)
        setSetupVisible(true)
      })
      .finally(() => setBootDone(true))

    // Initial liveness check
    checkJenkinsLiveness()

    // Poll every 30s for real Jenkins status
    const interval = setInterval(checkJenkinsLiveness, 30_000)
    return () => clearInterval(interval)
  }, [])

  // SSE event handler
  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.type === 'step') {
      const key = makeKey(event.job, event.build)
      setCards(prev => {
        const next = new Map(prev)
        const existing = next.get(key) ?? {
          key, job: event.job, build: event.build,
          steps: [], dismissed: false, createdAt: Date.now(),
        }
        const idx = existing.steps.findIndex(s => s.stage === event.stage)
        const steps = idx >= 0
          ? existing.steps.map((s, i) => i === idx ? event : s)
          : [...existing.steps, event]
        next.set(key, { ...existing, steps })
        return next
      })
    }

    if (event.type === 'analysis_complete') {
      const key = makeKey(event.job, event.build)
      setCards(prev => {
        const next = new Map(prev)
        const existing = next.get(key)
        if (existing) next.set(key, { ...existing, analysis: event, fixResult: undefined })
        return next
      })
    }

    if (event.type === 'fix_result') {
      const key = makeKey(event.job, event.build)
      setCards(prev => {
        const next = new Map(prev)
        const existing = next.get(key)
        if (existing) next.set(key, { ...existing, fixResult: event })
        return next
      })
    }

    if (event.type === 'jenkins_status') {
      setJenkinsStatus(event.ok ? 'connected' : 'disconnected')
    }

    if (event.type === 'build_success') {
      // Add a success card — user must explicitly discard to clear the job
      const successKey = makeKey(event.job, event.build)
      setCards(prev => {
        const next = new Map(prev)
        next.set(successKey, {
          key: successKey,
          job: event.job,
          build: event.build,
          steps: [],
          dismissed: false,
          createdAt: Date.now(),
          successEvent: event,
        })
        return next
      })
    }
  }, [])

  useEventStream(handleEvent)

  // Persist feed cards to localStorage on every change
  useEffect(() => {
    try {
      localStorage.setItem('pipeline_feed_cards', JSON.stringify(Array.from(cards.entries())))
    } catch { /* storage full — ignore */ }
  }, [cards])

  function dismissCard(key: string) {
    setCards(prev => {
      const next = new Map(prev)
      const existing = next.get(key)
      if (existing) next.set(key, { ...existing, dismissed: true })
      return next
    })
  }

  function clearFeed() {
    setCards(new Map())
    localStorage.removeItem('pipeline_feed_cards')
  }

  function discardJob(job: string) {
    if (!job) return
    setCards(prev => {
      const next = new Map(prev)
      for (const [k, card] of next.entries()) {
        if (card.job === job) next.delete(k)
      }
      return next
    })
  }

  function handleSetupSaved(repo: string) {
    setRepoName(repo)
    setIsConfigured(true)
    setSetupVisible(false)
    setProfilePicking(false)
    checkJenkinsLiveness()
  }

  function handleProfileSelected(profileId: string) {
    document.documentElement.classList.remove('dark')
    // Only wipe cards when switching profiles — not on initial selection
    if (activeProfileId && activeProfileId !== profileId) {
      setCards(new Map())
      localStorage.removeItem('pipeline_feed_cards')
    }
    setActiveProfileId(profileId)
    setIsConfigured(true)
    setProfilePicking(false)
    checkJenkinsLiveness()
  }

  const allCards = (() => {
    const visible = Array.from(cards.values()).filter(
      c => knownJobs.size === 0 || knownJobs.has(c.job)
    )
    // Group by job
    const groups = new Map<string, typeof visible>()
    for (const c of visible) {
      const g = groups.get(c.job) ?? []
      g.push(c)
      groups.set(c.job, g)
    }
    // Within each group: latest build number first
    for (const g of groups.values()) {
      g.sort((a, b) => Number(b.build) - Number(a.build))
    }
    // Sort groups: group whose latest build arrived most recently comes first
    const sortedGroups = Array.from(groups.values()).sort(
      (ga, gb) => gb[0].createdAt - ga[0].createdAt
    )
    return sortedGroups.flat()
  })()
  const cardList = allCards

  // Compute the latest failing build key per job.
  // A card qualifies if: analysis complete, no successEvent, not dismissed,
  // and is the highest build number for that job among such cards.
  const latestFailingKeys = (() => {
    const result = new Set<string>()
    const byJob = new Map<string, BuildCard>()
    for (const card of cards.values()) {
      if (!card.analysis || card.successEvent || card.dismissed) continue
      const current = byJob.get(card.job)
      if (!current || Number(card.build) > Number(current.build)) {
        byJob.set(card.job, card)
      }
    }
    for (const card of byJob.values()) {
      result.add(card.key)
    }
    return result
  })()

  // Track panel switches to trigger fade overlay
  const prevPanel = useRef<string>(activePanel)
  const [fadeKey, setFadeKey] = useState(0)
  useEffect(() => {
    if (prevPanel.current !== activePanel) {
      prevPanel.current = activePanel
      setFadeKey(k => k + 1)
    }
  }, [activePanel])

  if (!bootDone) return null

  if (profilePicking) {
    return (
      <ProfilePicker
        onSelect={handleProfileSelected}
        onAddNew={() => { setProfilePicking(false); setSetupVisible(true) }}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    )
  }

  return (
    <motion.div
      className="flex h-screen overflow-hidden bg-bg"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
    >
      <SetupWizard
        visible={setupVisible}
        onClose={() => { setSetupVisible(false); setProfilePicking(true) }}
        onSaved={handleSetupSaved}
      />

      <Sidebar
        active={activePanel}
        onNav={setActivePanel}
        onNewProject={() => setSetupVisible(true)}
        failureCount={latestFailingKeys.size}
      />

      <div className="flex flex-col flex-1 overflow-hidden">
        <Topbar
          activePanel={activePanel}
          repoName={repoName}
          jenkinsStatus={jenkinsStatus}
        />

        {/*
          All panels stay mounted — hidden via CSS so state is never lost.
          Chat messages, scroll position, and in-flight streams survive panel switches.
        */}
        <main className="flex-1 overflow-hidden relative">
          {/* Panel switch fade overlay */}
          <AnimatePresence>
            <motion.div
              key={fadeKey}
              className="absolute inset-0 z-10 bg-bg pointer-events-none"
              initial={{ opacity: 1 }}
              animate={{ opacity: 0 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
            />
          </AnimatePresence>

          <div className={activePanel === 'pipeline' ? 'h-full' : 'hidden'}>
            <PipelineFeed
              cards={cardList}
              latestFailingKeys={latestFailingKeys}
              onDismiss={dismissCard}
              onClearAll={clearFeed}
              onDiscardJob={discardJob}
              onOpenDetail={c => { setSelectedCard(c); setSelectedStage(null) }}
              onOpenDetailAtStage={(c, stage) => { setSelectedCard(c); setSelectedStage(stage) }}
              isConfigured={isConfigured}
              onConfigure={() => setSetupVisible(true)}
            />
          </div>
          <div className={activePanel === 'chat' ? 'h-full' : 'hidden'}>
            <ChatPanel
              chatStore={chatStore}
              streaming={chatStreaming}
              setStreaming={setChatStreaming}
            />
          </div>
          <div className={activePanel === 'jobs' ? 'h-full' : 'hidden'}>
            <JobsBrowser onJenkinsStatus={setJenkinsStatus} wireStatus={wireStatus} onWireStatus={handleWireStatus} isConfigured={isConfigured} onConfigure={() => setSetupVisible(true)} />
          </div>
          <div className={activePanel === 'settings' ? 'h-full' : 'hidden'}>
            <SettingsPanel onOpenSetup={() => setSetupVisible(true)} />
          </div>
        </main>
      </div>
      <BuildDetailDrawer
        card={selectedCard}
        onClose={() => { setSelectedCard(null); setSelectedStage(null) }}
        scrollToStage={selectedStage}
      />
    </motion.div>
  )
}
