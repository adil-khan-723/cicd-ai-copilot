import { useState, useCallback, useEffect } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { Topbar } from '@/components/Topbar'
import { SetupWizard } from '@/components/SetupWizard'
import { PipelineFeed } from '@/components/PipelineFeed'
import { ChatPanel } from '@/components/ChatPanel'
import { JobsBrowser } from '@/components/JobsBrowser'
import { SettingsPanel } from '@/components/SettingsPanel'
import { useEventStream } from '@/hooks/useEventStream'
import type { ActivePanel, BuildCard, ChatMessage, SSEEvent } from '@/types'

function makeKey(job: string, build: string | number) {
  return `${job}_${build}`
}

export default function App() {
  const [activePanel,   setActivePanel]   = useState<ActivePanel>('pipeline')
  const [setupVisible,  setSetupVisible]  = useState(false)
  const [repoName,      setRepoName]      = useState('')
  const [jenkinsStatus, setJenkinsStatus] = useState<'connected' | 'disconnected' | 'unknown'>('unknown')
  const [cards,         setCards]         = useState<Map<string, BuildCard>>(new Map())
  const [bootDone,      setBootDone]      = useState(false)

  // ── Chat state lifted here so it survives panel switches ─────────────────
  const [chatMessages,  setChatMessages]  = useState<ChatMessage[]>([])
  const [chatStreaming,  setChatStreaming]  = useState(false)

  // ── Jobs wire-up state lifted so it survives panel switches ───────────────
  const [wireStatus, setWireStatus] = useState<Record<string, 'ok' | 'already' | 'err'>>({})

  // ── Known Jenkins job names — used to filter phantom cards ────────────────
  const [knownJobs, setKnownJobs] = useState<Set<string>>(new Set())

  function handleWireStatus(name: string, status: 'ok' | 'already' | 'err') {
    setWireStatus(prev => ({ ...prev, [name]: status }))
  }

  // Bootstrap: fetch server settings on load
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(data => {
        if (data.github_repo) setRepoName(data.github_repo)
        if (data.configured) {
          setJenkinsStatus('connected')
          localStorage.setItem('devops_ai_configured', '1')
          localStorage.setItem('devops_ai_repo', data.github_repo ?? '')
        } else if (!localStorage.getItem('devops_ai_configured')) {
          setSetupVisible(true)
        }
      })
      .catch(() => {
        if (!localStorage.getItem('devops_ai_configured')) {
          setSetupVisible(true)
        } else {
          setRepoName(localStorage.getItem('devops_ai_repo') ?? '')
        }
      })
      .finally(() => setBootDone(true))

    // Fetch real job names from Jenkins to filter phantom cards
    fetch('/api/jobs')
      .then(r => r.json())
      .then(data => {
        const list: { name: string }[] = Array.isArray(data) ? data : (data.jobs ?? [])
        if (list.length > 0) setKnownJobs(new Set(list.map(j => j.name)))
      })
      .catch(() => { /* Jenkins not configured yet — show all cards */ })
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
        if (existing) next.set(key, { ...existing, analysis: event })
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

    if (event.type === 'build_success') {
      const successKey = makeKey(event.job, event.build)
      setCards(prev => {
        const next = new Map(prev)
        // Add success card (keep old failed cards — user will be prompted to discard)
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
  }

  function discardOldFailed(job: string) {
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
    setSetupVisible(false)
    setJenkinsStatus('connected')
  }

  const allCards = Array.from(cards.values()).sort((a, b) => b.createdAt - a.createdAt)
  // If Jenkins job list is loaded, hide cards for jobs not in Jenkins
  const cardList = knownJobs.size > 0
    ? allCards.filter(c => knownJobs.has(c.job))
    : allCards

  if (!bootDone) return null

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <SetupWizard
        visible={setupVisible}
        onClose={() => setSetupVisible(false)}
        onSaved={handleSetupSaved}
      />

      <Sidebar
        active={activePanel}
        onNav={setActivePanel}
        onNewProject={() => setSetupVisible(true)}
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
          <div className={activePanel === 'pipeline' ? 'h-full' : 'hidden'}>
            <PipelineFeed cards={cardList} onDismiss={dismissCard} onClearAll={clearFeed} onDiscardOldFailed={discardOldFailed} />
          </div>
          <div className={activePanel === 'chat' ? 'h-full' : 'hidden'}>
            <ChatPanel
              messages={chatMessages}
              setMessages={setChatMessages}
              streaming={chatStreaming}
              setStreaming={setChatStreaming}
            />
          </div>
          <div className={activePanel === 'jobs' ? 'h-full' : 'hidden'}>
            <JobsBrowser onJenkinsStatus={setJenkinsStatus} wireStatus={wireStatus} onWireStatus={handleWireStatus} />
          </div>
          <div className={activePanel === 'settings' ? 'h-full' : 'hidden'}>
            <SettingsPanel onOpenSetup={() => setSetupVisible(true)} />
          </div>
        </main>
      </div>
    </div>
  )
}
