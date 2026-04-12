import { useEffect, useRef } from 'react'
import type { SSEEvent } from '@/types'

/**
 * Opens a single SSE connection for the lifetime of the component.
 * Uses a ref for the callback so the EventSource is never torn down and
 * recreated when the parent re-renders (which would drop in-flight events).
 */
export function useEventStream(onEvent: (event: SSEEvent) => void) {
  const handlerRef = useRef(onEvent)
  handlerRef.current = onEvent   // always up-to-date, never stale

  useEffect(() => {
    const es = new EventSource('/events')

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as SSEEvent
        handlerRef.current(data)
      } catch {
        // ignore malformed events
      }
    }

    es.onerror = () => {
      // EventSource auto-reconnects on transient errors; no action needed
    }

    return () => {
      es.close()
    }
  }, [])  // empty deps: open once, never reopen due to callback identity changes
}
