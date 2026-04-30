import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Bot, User, CheckCircle2, Loader2, GitBranch, Sparkles,
  Copy, Check, Plus, Trash2, MessageSquare, ChevronLeft, ChevronRight,
  Pencil, PanelLeftClose, PanelLeftOpen,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { ChatMessage as Message } from '@/types'
import type { useChatStore } from '@/hooks/useChatStore'
import { PipelineCommitModal } from '@/components/PipelineCommitModal'
import { MissingCredentialModal } from '@/components/MissingCredentialModal'
import type { PendingCredential } from '@/components/PipelineCommitModal'

type ChatStore = ReturnType<typeof useChatStore>
type HistoryEntry = { role: 'user' | 'assistant'; content: string }

const EXAMPLES = [
  'Generate a Python CI pipeline for Jenkins with Docker build',
  'Create a GitHub Actions workflow for Node.js: test, build, push to ECR',
  'What causes "no space left on device" in Docker builds?',
  'Explain declarative vs scripted Jenkinsfile syntax',
]

function detectPipeline(text: string): { platform: 'jenkins' | 'github' | null; code: string | null } {
  const groovy = text.match(/```groovy\n([\s\S]+?)```/)
  if (groovy) return { platform: 'jenkins', code: groovy[1].trim() }
  const yaml = text.match(/```ya?ml\n([\s\S]+?)```/)
  if (yaml) {
    const code = yaml[1].trim()
    if (code.includes('jobs:') && (code.includes('runs-on:') || code.includes('steps:')))
      return { platform: 'github', code }
  }
  if (text.includes('pipeline {') && text.includes('stages {'))
    return { platform: 'jenkins', code: text }
  return { platform: null, code: null }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={handleCopy}
      title="Copy code"
      className="flex items-center gap-1 text-[10px] font-mono text-text-dim hover:text-text-primary transition-colors px-1.5 py-0.5 rounded"
    >
      {copied
        ? <><Check className="h-3 w-3 text-success" strokeWidth={2.5} /><span className="text-success">Copied</span></>
        : <><Copy className="h-3 w-3" strokeWidth={1.5} /><span>Copy</span></>}
    </button>
  )
}

function MessageContent({ content }: { content: string }) {
  const parts = content.split(/(```[\s\S]*?```)/g)
  return (
    <div className="space-y-2 whitespace-pre-wrap font-sans text-xs leading-relaxed">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const lang = part.match(/^```(\w+)/)?.[1] ?? ''
          const code = part.replace(/^```\w*\n?/, '').replace(/\n?```$/, '')
          return (
            <div key={i} className="rounded-lg border border-accent-border/20 overflow-hidden">
              <div className="px-3 py-1.5 bg-overlay/40 border-b border-accent-border/20 flex items-center justify-between gap-2">
                {lang
                  ? <span className="text-[10px] font-mono text-text-dim uppercase tracking-widest">{lang}</span>
                  : <span />}
                <CopyButton text={code} />
              </div>
              <pre className="px-3 py-2.5 text-[11px] font-mono text-text-primary bg-bg/60 overflow-x-auto leading-relaxed whitespace-pre">
                {code}
              </pre>
            </div>
          )
        }
        return part ? <span key={i}>{part}</span> : null
      })}
    </div>
  )
}

// ── Chat Sidebar ──────────────────────────────────────────────────────────────

interface SidebarProps {
  chatStore:  ChatStore
  collapsed:  boolean
  onToggle:   () => void
}

function ChatSidebar({ chatStore, collapsed, onToggle }: SidebarProps) {
  const { sessions, activeChatId, newChat, selectChat, deleteChat, renameChat } = chatStore
  const [hoveredId,   setHoveredId]   = useState<string | null>(null)
  const [renamingId,  setRenamingId]  = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const sorted = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)

  function startRename(e: React.MouseEvent, id: string, currentTitle: string) {
    e.stopPropagation()
    setRenamingId(id)
    setRenameValue(currentTitle)
  }

  function commitRename(id: string) {
    renameChat(id, renameValue)
    setRenamingId(null)
  }

  return (
    <div
      className={cn(
        'flex flex-col border-r border-accent-border/30 bg-sidebar shrink-0 transition-all duration-200',
        collapsed ? 'w-10' : 'w-56'
      )}
    >
      {/* Header row: title + collapse button */}
      <div className={cn(
        'flex items-center border-b border-accent-border/20 shrink-0',
        collapsed ? 'justify-center h-10' : 'justify-between px-2.5 h-10'
      )}>
        {!collapsed && (
          <span className="text-[11px] font-semibold text-text-dim uppercase tracking-widest">Chats</span>
        )}
        <button
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="h-6 w-6 flex items-center justify-center rounded-md hover:bg-accent/10 transition-colors text-text-dim hover:text-text-muted"
        >
          {collapsed
            ? <PanelLeftOpen  className="h-3.5 w-3.5" strokeWidth={1.5} />
            : <PanelLeftClose className="h-3.5 w-3.5" strokeWidth={1.5} />}
        </button>
      </div>

      {!collapsed && (
        <>
          {/* New chat button */}
          <div className="p-2 border-b border-accent-border/20 shrink-0">
            <button
              onClick={() => newChat()}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[12px] font-medium text-text-muted hover:text-accent hover:bg-accent/8 transition-all duration-150 group"
            >
              <Plus className="h-3.5 w-3.5 shrink-0" strokeWidth={2.5} />
              New chat
            </button>
          </div>

          {/* Session list */}
          <div className="flex-1 overflow-y-auto py-1">
            {sorted.length === 0 && (
              <p className="text-[11px] text-text-dim text-center mt-8 px-3 leading-relaxed">
                No chats yet.
              </p>
            )}
            <AnimatePresence initial={false}>
              {sorted.map(session => (
                <motion.div
                  key={session.id}
                  layout
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8, transition: { duration: 0.1 } }}
                  transition={{ duration: 0.15 }}
                  className={cn(
                    'group relative flex items-center gap-1.5 mx-1.5 my-0.5 px-2 py-1.5 rounded-lg cursor-pointer transition-all duration-150',
                    session.id === activeChatId
                      ? 'bg-accent/10 text-text-primary'
                      : 'text-text-muted hover:bg-surface hover:text-text-base'
                  )}
                  onMouseEnter={() => setHoveredId(session.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => { if (renamingId !== session.id) selectChat(session.id) }}
                >
                  <MessageSquare className="h-3 w-3 shrink-0 opacity-40 mt-px" strokeWidth={1.5} />

                  {renamingId === session.id ? (
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={e => setRenameValue(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter')  { e.preventDefault(); commitRename(session.id) }
                        if (e.key === 'Escape') { setRenamingId(null) }
                      }}
                      onBlur={() => commitRename(session.id)}
                      onClick={e => e.stopPropagation()}
                      className="flex-1 min-w-0 text-[11px] font-medium bg-card border border-accent-border rounded px-1 py-0 outline-none text-text-primary"
                    />
                  ) : (
                    <span className="flex-1 min-w-0 text-[11px] font-medium truncate leading-tight">
                      {session.title}
                    </span>
                  )}

                  {/* Action buttons: rename + delete — show on hover or active */}
                  {renamingId !== session.id && (hoveredId === session.id || session.id === activeChatId) && (
                    <div className="flex items-center gap-0.5 shrink-0">
                      <button
                        onClick={e => startRename(e, session.id, session.title)}
                        title="Rename"
                        className="h-5 w-5 flex items-center justify-center rounded hover:text-accent transition-colors"
                      >
                        <Pencil className="h-2.5 w-2.5" strokeWidth={1.5} />
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); deleteChat(session.id) }}
                        title="Delete chat"
                        className="h-5 w-5 flex items-center justify-center rounded hover:text-error transition-colors"
                      >
                        <Trash2 className="h-2.5 w-2.5" strokeWidth={1.5} />
                      </button>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </>
      )}

      {/* Collapsed: new chat icon only */}
      {collapsed && (
        <div className="flex flex-col items-center pt-1 gap-1">
          <button
            onClick={() => newChat()}
            title="New chat"
            className="h-7 w-7 flex items-center justify-center rounded-lg hover:bg-accent/10 transition-colors text-text-dim hover:text-accent"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2.5} />
          </button>
        </div>
      )}
    </div>
  )
}

// ── No-chat landing screen ────────────────────────────────────────────────────

function NoChatSelected({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-5 select-none text-center px-8">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-accent shadow-lifted">
        <Sparkles className="h-6 w-6 text-white" strokeWidth={2} />
      </div>
      <div>
        <p className="text-sm font-semibold text-text-primary">AI Copilot</p>
        <p className="text-xs text-text-dim mt-1.5 max-w-xs leading-relaxed">
          Select a chat from the sidebar or start a new one.
        </p>
      </div>
      <button
        onClick={onNew}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-[12px] font-semibold hover:bg-accent-hi transition-colors shadow-sm"
      >
        <Plus className="h-3.5 w-3.5" strokeWidth={2.5} />
        New chat
      </button>
    </div>
  )
}

// ── Main ChatPanel ────────────────────────────────────────────────────────────

interface ChatPanelProps {
  chatStore:    ChatStore
  streaming:    boolean
  setStreaming: React.Dispatch<React.SetStateAction<boolean>>
}

export function ChatPanel({ chatStore, streaming, setStreaming }: ChatPanelProps) {
  const { activeChatId, activeSession, newChat, setMessages } = chatStore
  const messages: Message[] = activeSession?.messages ?? []

  const [input,            setInput]            = useState('')
  const [commitTarget,     setCommitTarget]     = useState<Message | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [pendingCreds,     setPendingCreds]     = useState<{ items: PendingCredential[]; jobName: string } | null>(null)
  const [credIdx,          setCredIdx]          = useState(0)
  // Once user interacts with suggestions (clicks one or starts typing), hide them
  const [suggestionsGone,  setSuggestionsGone]  = useState(false)
  const bottomRef   = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Reset suggestion state when switching chats
  useEffect(() => { setSuggestionsGone(false) }, [activeChatId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const showSuggestions = activeChatId && messages.length === 0 && !suggestionsGone

  async function sendMessage(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return

    const chatId = activeChatId || newChat()
    setSuggestionsGone(true)

    const userMsg: Message      = { id: `u${Date.now()}`, role: 'user',      content: msg }
    const assistantId           = `a${Date.now() + 1}`
    const assistantMsg: Message = { id: assistantId,      role: 'assistant', content: '', isStreaming: true }

    setMessages(chatId, m => [...m, userMsg, assistantMsg])
    setInput('')
    setStreaming(true)

    const history: HistoryEntry[] = messages.map(m => ({ role: m.role, content: m.content }))

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history }),
      })
      if (!res.body) throw new Error('No response body')

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let full = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        full += decoder.decode(value, { stream: true })
        setMessages(chatId, m => m.map(x => x.id === assistantId ? { ...x, content: full } : x))
      }

      const { platform, code } = detectPipeline(full)
      setMessages(chatId, m => m.map(x =>
        x.id === assistantId
          ? { ...x, content: full, isStreaming: false, pipeline: code ?? undefined, pipelinePlatform: platform ?? undefined }
          : x
      ))
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      setMessages(chatId, m => m.map(x =>
        x.id === assistantId ? { ...x, content: `Error: ${errMsg}`, isStreaming: false } : x
      ))
    } finally {
      setStreaming(false)
      textareaRef.current?.focus()
    }
  }

  function handleCommitted(pending: PendingCredential[]) {
    if (!commitTarget || !activeChatId) return
    const jobName = commitTarget.content.slice(0, 80)
    setMessages(activeChatId, m => m.map(x => x.id === commitTarget.id ? { ...x, committed: true } : x))
    setCommitTarget(null)
    if (pending.length > 0) {
      setPendingCreds({ items: pending, jobName })
      setCredIdx(0)
    }
  }

  async function handleCredDone(credentialId: string, credFields: import('@/types').CredentialFields | null) {
    if (credFields) {
      try {
        await fetch('/api/fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fix_type:        'configure_credential',
            job_name:        pendingCreds?.jobName ?? '',
            build_number:    '0',
            credential_id:   credentialId,
            credential_type: credFields.credential_type,
            secret_value:    credFields.secret_value,
            username:        credFields.username,
            password:        credFields.password,
            ssh_username:    credFields.ssh_username,
            private_key:     credFields.private_key,
            skip_retrigger:  'true',
          }),
        })
      } catch {
        // fail-silent: credential creation best-effort
      }
    }
    if (!pendingCreds) return
    const nextIdx = credIdx + 1
    if (nextIdx >= pendingCreds.items.length) {
      setPendingCreds(null)
      setCredIdx(0)
    } else {
      setCredIdx(nextIdx)
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar */}
      <ChatSidebar
        chatStore={chatStore}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(c => !c)}
      />

      {/* Main area */}
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">

        {/* No chat selected */}
        {!activeChatId && (
          <NoChatSelected onNew={() => newChat()} />
        )}

        {/* Chat selected */}
        {activeChatId && (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">

              {/* Suggestions — only when chat is empty and user hasn't dismissed */}
              <AnimatePresence>
                {showSuggestions && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8, transition: { duration: 0.15 } }}
                    className="flex flex-col items-center justify-center h-full gap-5 select-none"
                  >
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-accent shadow-lifted">
                      <Sparkles className="h-6 w-6 text-white" strokeWidth={2} />
                    </div>
                    <div className="text-center">
                      <p className="text-sm font-semibold text-text-primary">Copilot Chat</p>
                      <p className="text-xs text-text-dim mt-1.5 max-w-xs leading-relaxed">
                        Ask anything — DevOps questions, pipeline generation, failure analysis.
                      </p>
                    </div>
                    <div className="flex flex-col gap-1.5 w-full max-w-sm">
                      {EXAMPLES.map(ex => (
                        <button
                          key={ex}
                          onClick={() => { setSuggestionsGone(true); sendMessage(ex) }}
                          title={ex}
                          className="text-[11px] text-text-muted font-mono border border-accent-border/30 rounded-lg px-3 py-2 bg-surface hover:bg-card hover:border-accent-border hover:text-text-primary transition-all duration-150 text-left truncate cursor-pointer"
                        >
                          {ex}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Messages */}
              <AnimatePresence initial={false}>
                {messages.map(msg => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                    className={cn('flex gap-2.5', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
                  >
                    <div className={cn(
                      'flex h-6 w-6 shrink-0 items-center justify-center rounded-lg mt-0.5',
                      msg.role === 'user'
                        ? 'bg-surface border border-accent-border/30'
                        : 'bg-gradient-accent shadow-sm'
                    )}>
                      {msg.role === 'user'
                        ? <User className="h-3 w-3 text-text-muted" strokeWidth={1.5} />
                        : <Bot  className="h-3 w-3 text-white"      strokeWidth={2} />}
                    </div>

                    <div className={cn('max-w-[82%] space-y-2', msg.role === 'user' ? 'items-end flex flex-col' : '')}>
                      <div className={cn(
                        'rounded-xl px-3.5 py-2.5',
                        msg.role === 'user'
                          ? 'bg-card border border-accent-border/30 text-text-primary'
                          : 'bg-surface border border-accent-border/20 text-text-primary'
                      )}>
                        {msg.isStreaming && !msg.content ? (
                          <div className="flex items-center gap-2 text-text-dim">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span className="text-xs font-mono">Thinking...</span>
                          </div>
                        ) : (
                          <MessageContent content={msg.content} />
                        )}
                      </div>

                      {msg.pipeline && !msg.committed && (
                        <Button variant="success" size="sm" onClick={() => setCommitTarget(msg)} className="gap-1.5">
                          <GitBranch className="h-3 w-3" strokeWidth={2} />
                          Approve &amp; Send to Jenkins
                        </Button>
                      )}

                      {msg.committed && (
                        <div className="flex items-center gap-1.5 text-xs text-success font-mono">
                          <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />
                          Committed and applied
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
              <div ref={bottomRef} />
            </div>

            <PipelineCommitModal
              open={commitTarget !== null}
              pipeline={commitTarget?.pipeline ?? ''}
              platform={commitTarget?.pipelinePlatform ?? 'jenkins'}
              description={commitTarget?.content.slice(0, 120) ?? 'Generated pipeline'}
              onCommitted={handleCommitted}
              onCancel={() => setCommitTarget(null)}
            />

            {pendingCreds && (
              <MissingCredentialModal
                open={true}
                pending={pendingCreds.items[credIdx]}
                jobName={pendingCreds.jobName}
                index={credIdx}
                total={pendingCreds.items.length}
                onDone={handleCredDone}
                onSkipAll={() => { setPendingCreds(null); setCredIdx(0) }}
              />
            )}

            {/* Input */}
            <div className="shrink-0 border-t border-accent-border/30 p-3">
              <div className="flex gap-2 items-end">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => { setInput(e.target.value); if (e.target.value) setSuggestionsGone(true) }}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
                  placeholder="Ask anything... (Enter to send, Shift+Enter for newline)"
                  rows={2}
                  className="flex-1 text-xs"
                  disabled={streaming}
                />
                <Button
                  size="icon"
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || streaming}
                >
                  {streaming
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <Send className="h-4 w-4" strokeWidth={2} />}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
