import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Bot, User, CheckCircle2, Loader2, GitBranch, Sparkles, Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { ChatMessage as Message } from '@/types'
import { PipelineCommitModal } from '@/components/PipelineCommitModal'

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
            <div key={i} className="rounded-lg border border-glass overflow-hidden">
              <div className="px-3 py-1.5 bg-white/5 border-b border-glass flex items-center justify-between gap-2">
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

interface ChatPanelProps {
  messages:    Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  streaming:   boolean
  setStreaming: React.Dispatch<React.SetStateAction<boolean>>
}

export function ChatPanel({ messages, setMessages, streaming, setStreaming }: ChatPanelProps) {
  const [input,        setInput]        = useState('')
  const [commitTarget, setCommitTarget] = useState<Message | null>(null)
  const bottomRef   = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function sendMessage(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return

    const userMsg: Message     = { id: `u${Date.now()}`, role: 'user',      content: msg }
    const assistantId          = `a${Date.now() + 1}`
    const assistantMsg: Message = { id: assistantId,     role: 'assistant', content: '', isStreaming: true }

    setMessages(m => [...m, userMsg, assistantMsg])
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
        setMessages(m => m.map(x => x.id === assistantId ? { ...x, content: full } : x))
      }

      const { platform, code } = detectPipeline(full)
      setMessages(m => m.map(x =>
        x.id === assistantId
          ? { ...x, content: full, isStreaming: false, pipeline: code ?? undefined, pipelinePlatform: platform ?? undefined }
          : x
      ))
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      setMessages(m => m.map(x =>
        x.id === assistantId ? { ...x, content: `Error: ${errMsg}`, isStreaming: false } : x
      ))
    } finally {
      setStreaming(false)
      textareaRef.current?.focus()
    }
  }

  function handleCommitted() {
    if (!commitTarget) return
    setMessages(m => m.map(x => x.id === commitTarget.id ? { ...x, committed: true } : x))
    setCommitTarget(null)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-5 select-none">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-accent shadow-glow-accent">
              <Sparkles className="h-6 w-6 text-white" strokeWidth={2} />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-text-primary">Copilot Chat</p>
              <p className="text-xs text-text-dim mt-1.5 max-w-xs leading-relaxed">
                Ask anything — DevOps questions, pipeline generation, failure analysis, or engineering advice.
              </p>
            </div>
            <div className="flex flex-col gap-1.5 w-full max-w-sm">
              {EXAMPLES.map(ex => (
                <button
                  key={ex}
                  onClick={() => sendMessage(ex)}
                  title={ex}
                  className="text-[11px] text-text-muted font-mono border border-glass rounded-lg px-3 py-2 bg-surface hover:bg-card hover:border-glass-hi hover:text-text-primary transition-all duration-150 text-left truncate cursor-pointer"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map(msg => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 400, damping: 35 }}
              className={cn('flex gap-2.5', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
            >
              {/* Avatar */}
              <div className={cn(
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-lg mt-0.5',
                msg.role === 'user'
                  ? 'bg-surface border border-glass'
                  : 'bg-gradient-accent shadow-glow-accent'
              )}>
                {msg.role === 'user'
                  ? <User className="h-3 w-3 text-text-muted" strokeWidth={1.5} />
                  : <Bot  className="h-3 w-3 text-white"      strokeWidth={2} />}
              </div>

              {/* Bubble */}
              <div className={cn('max-w-[82%] space-y-2', msg.role === 'user' ? 'items-end flex flex-col' : '')}>
                <div className={cn(
                  'rounded-xl px-3.5 py-2.5',
                  msg.role === 'user'
                    ? 'bg-card border border-glass-hi text-text-primary'
                    : 'bg-surface border border-glass text-text-primary'
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
                  <Button
                    variant="success"
                    size="sm"
                    onClick={() => setCommitTarget(msg)}
                    className="gap-1.5"
                  >
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

      {/* Input */}
      <div className="shrink-0 border-t border-glass p-3">
        <div className="flex gap-2 items-end">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
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
    </div>
  )
}
