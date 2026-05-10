import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { SettingsPanel } from '../SettingsPanel'

function mockSettings(overrides: Record<string, unknown> = {}) {
  global.fetch = vi.fn((url: string) => {
    if (typeof url === 'string' && url.includes('/api/settings')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          jenkins_url: 'http://j',
          jenkins_user: 'admin',
          llm_provider: 'ollama',
          configured: true,
          webhook_secret_set: true,
          anthropic_configured: false,
          anthropic_key_preview: '',
          anthropic_analysis_model: '',
          anthropic_generation_model: '',
          ollama_base_url: 'http://localhost:11434',
          analysis_model: 'llama3.1:8b',
          generation_model: 'qwen2.5-coder:14b',
          ...overrides,
        }),
      } as Response)
    }
    if (typeof url === 'string' && url.includes('/api/audit')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ entries: [] }) } as Response)
    }
    if (typeof url === 'string' && url.includes('/api/health')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) } as Response)
    }
    return Promise.resolve({ ok: false, json: () => Promise.resolve({}) } as Response)
  }) as unknown as typeof fetch
}

describe('SettingsPanel LlmConfig', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders LLM Configuration card with provider selector', async () => {
    mockSettings()
    render(<SettingsPanel onOpenSetup={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/LLM Configuration/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Anthropic \(cloud\)/i)).toBeInTheDocument()
    expect(screen.getByText(/Ollama \(local\)/i)).toBeInTheDocument()
  })

  it('shows masked saved key preview when anthropic configured', async () => {
    mockSettings({
      llm_provider: 'anthropic',
      anthropic_configured: true,
      anthropic_key_preview: 'sk-ant-•••...•••wxyz',
    })
    render(<SettingsPanel onOpenSetup={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/sk-ant-•••...•••wxyz/)).toBeInTheDocument()
    })
  })

  it('exposes Test Connection and Save buttons', async () => {
    mockSettings()
    render(<SettingsPanel onOpenSetup={() => {}} />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /test connection/i })).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /^save$/i })).toBeInTheDocument()
  })
})

vi.mock('framer-motion', async () => {
  const React = await import('react')
  return {
    motion: new Proxy({}, {
      get: (_t, prop: string) => React.forwardRef(({ children, ...props }: any, ref: any) =>
        React.createElement(prop as string, { ...props, ref }, children)
      ),
    }),
    AnimatePresence: ({ children }: any) => children,
  }
})
