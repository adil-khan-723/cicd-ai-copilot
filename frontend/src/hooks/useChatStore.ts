import { useState, useEffect, useCallback } from 'react'
import type { ChatSession, ChatMessage } from '@/types'

function storageKey(profileId: string) {
  return `devops_ai_chats:${profileId}`
}

function load(profileId: string): ChatSession[] {
  if (!profileId) return []
  try {
    const raw = localStorage.getItem(storageKey(profileId))
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function save(profileId: string, sessions: ChatSession[]) {
  if (!profileId) return
  try {
    // keep only last 100 sessions, trim each to last 200 messages
    const trimmed = sessions.slice(-100).map(s => ({
      ...s,
      messages: s.messages.filter(m => !m.isStreaming).slice(-200),
    }))
    localStorage.setItem(storageKey(profileId), JSON.stringify(trimmed))
  } catch {}
}

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function autoTitle(messages: ChatMessage[]): string {
  const first = messages.find(m => m.role === 'user')
  if (!first) return 'New chat'
  const text = first.content.trim()
  return text.slice(0, 45) + (text.length > 45 ? '…' : '')
}

export function useChatStore(profileId: string) {
  const [sessions, setSessions] = useState<ChatSession[]>(() => load(profileId))
  const [activeChatId, setActiveChatId] = useState<string>(() => {
    const s = load(profileId)
    return s.length > 0 ? s[s.length - 1].id : ''
  })

  // Reload when profile switches
  useEffect(() => {
    const s = load(profileId)
    setSessions(s)
    setActiveChatId(s.length > 0 ? s[s.length - 1].id : '')
  }, [profileId])

  // Persist on every change
  useEffect(() => {
    save(profileId, sessions)
  }, [sessions, profileId])

  const activeSession = sessions.find(s => s.id === activeChatId) ?? null

  const newChat = useCallback((): string => {
    const id = makeId()
    const session: ChatSession = {
      id,
      title: 'New chat',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    }
    setSessions(prev => [...prev, session])
    setActiveChatId(id)
    return id
  }, [])

  const selectChat = useCallback((id: string) => {
    setActiveChatId(id)
  }, [])

  const deleteChat = useCallback((id: string) => {
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id)
      // If we deleted the active chat, switch to most recent remaining
      if (id === activeChatId) {
        const last = next[next.length - 1]
        setActiveChatId(last?.id ?? '')
      }
      return next
    })
  }, [activeChatId])

  const setMessages = useCallback((
    id: string,
    updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])
  ) => {
    setSessions(prev => prev.map(s => {
      if (s.id !== id) return s
      const next = typeof updater === 'function' ? updater(s.messages) : updater
      return {
        ...s,
        messages: next,
        title: autoTitle(next),
        updatedAt: Date.now(),
      }
    }))
  }, [])

  const renameChat = useCallback((id: string, title: string) => {
    const trimmed = title.trim()
    if (!trimmed) return
    setSessions(prev => prev.map(s =>
      s.id === id ? { ...s, title: trimmed, updatedAt: Date.now() } : s
    ))
  }, [])

  return {
    sessions,
    activeChatId,
    activeSession,
    newChat,
    selectChat,
    deleteChat,
    renameChat,
    setMessages,
  }
}
