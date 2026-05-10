import { useState, useEffect, useCallback } from 'react'
import type { AvailableModel } from '@/types'

interface AvailableModelsState {
  models: AvailableModel[]
  defaultProvider: string
  defaultModel: string
  loading: boolean
  refresh: () => void
}

/**
 * Fetches /api/llm/available-models. Refreshable on demand.
 * Returns all reachable + offline-but-configured models across providers.
 */
export function useAvailableModels(): AvailableModelsState {
  const [models, setModels] = useState<AvailableModel[]>([])
  const [defaultProvider, setDefaultProvider] = useState('')
  const [defaultModel, setDefaultModel] = useState('')
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(() => {
    setLoading(true)
    fetch('/api/llm/available-models')
      .then(r => r.json())
      .then(d => {
        setModels(d.models ?? [])
        setDefaultProvider(d.default_provider ?? '')
        setDefaultModel(d.default_analysis_model ?? '')
      })
      .catch(() => {
        setModels([])
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return { models, defaultProvider, defaultModel, loading, refresh }
}
