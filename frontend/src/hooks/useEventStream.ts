import { useEffect } from 'react'
import type { SSEEvent } from '@/types'

export function useEventStream(onEvent: (event: SSEEvent) => void) {
  useEffect(() => {
    const es = new EventSource('/events')

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as SSEEvent
        onEvent(data)
      } catch {
        // ignore malformed events
      }
    }

    es.onerror = () => {
      // EventSource auto-reconnects; no action needed
    }

    return () => {
      es.close()
    }
  }, [onEvent])
}
