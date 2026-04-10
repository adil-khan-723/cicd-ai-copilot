import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Bot, User, CheckCircle2, Loader2, GitBranch } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

interface HistoryEntry {
  role: 'user' | 'assistant'
  content: string
}

interface Message extends HistoryEntry {
  id: string
  pipeline?: string
  pipelinePlatform?: 'jenkins' | 'github'
  committed?: boolean
  isStreaming?: boolean
}

const EXAMPLES = [
  'Generate a Python CI pipeline for Jenkins with Docker build and ECR push',
  'Create a GitHub Actions workflow for Node.js: test, build Docker, push to ECR',
  'Explain what a Jenkinsfile declarative pipeline looks like',
  'What causes a "no space left on device" error in Docker builds?',
  'How do I add Slack notifications to my Jenkins pipeline?',
]

function detectPipeline(text: string): { platform: 'jenkins' | 'github' | null; code: string | null } {
  const groovyMatch = text.match(/```groovy\n([\s\S]+?)```/)
  if (groovyMatch) return { platform: 'jenkins', code: groovyMatch[1].trim() }

  const yamlMatch = text.match(/```ya?ml\n([\s\S]+?)```/)
  if (yamlMatch) {
    const code = yamlMatch[1].trim()
    if (code.includes('jobs:') && (code.includes('runs-on:') || code.includes('steps:')))
      return { platform: 'github', code }
  }

  // Fallback: unwrapped pipeline
  if (text.includes('pipeline {') && text.includes('stages {'))
    return { platform: 'jenkins', code: text }

  return { platform: null, code: null }
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [committing, setCommitting] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return

    const userMsg: Message = { id: `u${Date.now()}`, role: 'user', content: msg }
    const assistantId = `a${Date.now() + 1}`
    const assistantMsg: Message = { id: assistantId, role: 'assistant', content: '', isStreaming: true }

    setMessages((m) => [...m, userMsg, assistantMsg])
    setInput('')
    setStreaming(true)

    // Build history from existing messages (exclude the new empty assistant slot)
    const history: HistoryEntry[] = messages.map((m) => ({ role: m.role, content: m.content }))

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history }),
      })

      if (!res.body) throw new Error('No response body')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let full = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        full += decoder.decode(value, { stream: true })
        setMessages((m) =>
          m.map((x) => (x.id === assistantId ? { ...x, content: full } : x))
        )
      }

      // Detect pipeline code
      const { platform, code } = detectPipeline(full)
      setMessages((m) =>
        m.map((x) =>
          x.id === assistantId
            ? { ...x, content: full, isStreaming: false, pipeline: code ?? undefined, pipelinePlatform: platform ?? undefined }
            : x
        )
      )
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      setMessages((m) =>
        m.map((x) =>
          x.id === assistantId
            ? { ...x, content: `Error: ${errMsg}`, isStreaming: false }
            : x
        )
      )
    } finally {
      setStreaming(false)
      textareaRef.current?.focus()
    }
  }

  async function commitPipeline(msg: Message) {
    if (!msg.pipeline) return
    setCommitting(msg.id)
    try {
      await fetch('/api/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: msg.pipelinePlatform ?? 'jenkins',
          content: msg.pipeline,
          description: 'Generated pipeline from Copilot chat',
          apply_to_jenkins: msg.pipelinePlatform === 'jenkins',
        }),
      })
      setMessages((m) => m.map((x) => (x.id === msg.id ? { ...x, committed: true } : x)))
    } catch {
      // silently ignore; user can retry
    } finally {
      setCommitting(null)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-text-dim">
            <Bot className="h-9 w-9 opacity-20" />
            <div className="text-center">
              <p className="text-sm font-semibold text-text-muted">Copilot Chat</p>
              <p className="text-xs mt-1 text-text-dim max-w-xs leading-relaxed">
                Ask anything — DevOps questions, pipeline generation, failure analysis, or
                general engineering advice.
              </p>
            </div>
            <div className="flex flex-col gap-1.5 w-full max-w-sm mt-1">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => sendMessage(ex)}
                  className="text-xs text-text-dim hover:text-text-muted font-mono border border-border rounded px-3 py-2 bg-surface hover:bg-white/5 transition-colors text-left truncate"
                  title={ex}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn('flex gap-2.5', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
            >
              {/* Avatar */}
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-border bg-surface mt-0.5">
                {msg.role === 'user' ? (
                  <User className="h-3 w-3 text-text-muted" />
                ) : (
                  <Bot className="h-3 w-3 text-text-muted" />
                )}
              </div>

              {/* Bubble */}
              <div className={cn('max-w-[82%] space-y-2', msg.role === 'user' ? 'items-end flex flex-col' : 'items-start')}>
                <div
                  className={cn(
                    'rounded-lg px-3 py-2.5 text-xs leading-relaxed',
                    msg.role === 'user'
                      ? 'bg-white/5 text-text-primary border border-border'
                      : 'bg-surface text-text-primary border border-border-subtle'
                  )}
                >
                  {msg.isStreaming && !msg.content ? (
                    <span className="flex items-center gap-1.5 text-text-dim">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      <span>Thinking...</span>
                    </span>
                  ) : (
                    <MessageContent content={msg.content} />
                  )}
                </div>

                {/* Pipeline commit button */}
                {msg.pipeline && !msg.committed && (
                  <Button
                    size="sm"
                    variant="success"
                    onClick={() => commitPipeline(msg)}
                    disabled={committing === msg.id}
                    className="gap-1.5"
                  >
                    {committing === msg.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <GitBranch className="h-3 w-3" />
                    )}
                    Approve &amp; Commit
                    {msg.pipelinePlatform === 'jenkins' ? ' + Apply to Jenkins' : ' to GitHub'}
                  </Button>
                )}

                {msg.committed && (
                  <div className="flex items-center gap-1.5 text-xs text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Committed and applied
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-border p-3">
        <div className="flex gap-2 items-end">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
            placeholder="Ask anything... (Enter to send, Shift+Enter for newline)"
            rows={2}
            className="flex-1 text-xs"
            disabled={streaming}
          />
          <Button size="icon" onClick={() => sendMessage()} disabled={!input.trim() || streaming}>
            {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  )
}

// Renders assistant content: detects code blocks and renders them with monospace
function MessageContent({ content }: { content: string }) {
  const parts = content.split(/(```[\s\S]*?```)/g)
  return (
    <div className="space-y-2 whitespace-pre-wrap font-sans">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const langMatch = part.match(/^```(\w+)?/)
          const lang = langMatch?.[1] ?? ''
          const code = part.replace(/^```\w*\n?/, '').replace(/```$/, '')
          return (
            <pre
              key={i}
              className="font-mono text-[11px] bg-black/40 border border-border rounded p-2.5 overflow-x-auto leading-relaxed text-text-primary whitespace-pre"
            >
              {lang && <span className="text-text-dim text-[10px] block mb-1 uppercase">{lang}</span>}
              {code}
            </pre>
          )
        }
        return part ? <span key={i}>{part}</span> : null
      })}
    </div>
  )
}
