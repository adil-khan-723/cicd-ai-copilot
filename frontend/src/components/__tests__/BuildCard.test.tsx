import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BuildCard } from '../BuildCard'
import type { BuildCard as BuildCardType, AnalysisCompleteEvent } from '@/types'

function makeAnalysis(overrides: Partial<AnalysisCompleteEvent> = {}): AnalysisCompleteEvent {
  return {
    type: 'analysis_complete',
    job: 'demo',
    build: 1,
    failed_stage: 'Test',
    root_cause: 'Tool missing',
    fix_suggestion: 'Patch the tool name',
    steps: ['Open Manage Jenkins', 'Click Tools', 'Configure Maven'],
    fix_type: 'configure_tool',
    confidence: 0.9,
    log_excerpt: 'ERROR: tool not found',
    pipeline_stages: [{ name: 'Test', status: 'failed' }],
    ...overrides,
  }
}

function makeCard(overrides: Partial<BuildCardType> = {}, analysisOverrides: Partial<AnalysisCompleteEvent> = {}): BuildCardType {
  return {
    key: 'demo-1',
    job: 'demo',
    build: 1,
    steps: [],
    analysis: makeAnalysis(analysisOverrides),
    dismissed: false,
    createdAt: Date.now(),
    ...overrides,
  }
}

const noop = () => {}

describe('BuildCard button gating', () => {
  it('renders Apply Fix when fix_type is auto-fixable + high confidence + latest failing', () => {
    render(
      <BuildCard
        card={makeCard()}
        isLatestFailing
        onDismiss={noop}
        onOpenDetail={noop}
      />
    )
    expect(screen.getByRole('button', { name: /apply fix/i })).toBeInTheDocument()
  })

  it('hides Apply Fix when not isLatestFailing', () => {
    render(
      <BuildCard
        card={makeCard()}
        isLatestFailing={false}
        onDismiss={noop}
        onOpenDetail={noop}
      />
    )
    expect(screen.queryByRole('button', { name: /apply fix/i })).not.toBeInTheDocument()
  })

  it('hides Apply Fix when confidence is below 0.75', () => {
    render(
      <BuildCard
        card={makeCard({}, { confidence: 0.5 })}
        isLatestFailing
        onDismiss={noop}
        onOpenDetail={noop}
      />
    )
    expect(screen.queryByRole('button', { name: /apply fix/i })).not.toBeInTheDocument()
  })

  it('shows See Suggestion button (not Apply Fix) when fix_type is diagnostic_only', () => {
    render(
      <BuildCard
        card={makeCard({}, { fix_type: 'diagnostic_only' })}
        isLatestFailing
        onDismiss={noop}
        onOpenDetail={noop}
      />
    )
    expect(screen.queryByRole('button', { name: /apply fix/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /see suggestion/i })).toBeInTheDocument()
  })

  it('shows Retry Fix label when previous fix_result.success was false', () => {
    const card = makeCard({
      fixResult: {
        type: 'fix_result',
        job: 'demo',
        build: 1,
        fix_type: 'configure_tool',
        success: false,
        detail: 'patch failed',
      },
    })
    render(
      <BuildCard
        card={card}
        isLatestFailing
        onDismiss={noop}
        onOpenDetail={noop}
      />
    )
    expect(screen.getByRole('button', { name: /retry fix/i })).toBeInTheDocument()
  })

  it('hides Apply Fix permanently when fix_result.success was true', () => {
    const card = makeCard({
      fixResult: {
        type: 'fix_result',
        job: 'demo',
        build: 1,
        fix_type: 'configure_tool',
        success: true,
        detail: 'patched',
      },
    })
    render(
      <BuildCard
        card={card}
        isLatestFailing
        onDismiss={noop}
        onOpenDetail={noop}
      />
    )
    expect(screen.queryByRole('button', { name: /apply fix/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /retry fix/i })).not.toBeInTheDocument()
  })

  it('shows Fix N related issues button when primary diagnostic + fixable potentials exist', () => {
    render(
      <BuildCard
        card={makeCard({}, {
          fix_type: 'diagnostic_only',
          potential_issues: [
            { type: 'config', line: 'credentials("x")', issue: 'missing', fix_type: 'configure_credential', confidence: 'confirmed' },
            { type: 'syntax', line: "sh 'mvn clen'", issue: 'typo', fix_type: 'fix_step_typo', confidence: 'llm_only', correct_line: "sh 'mvn clean'" },
          ],
        })}
        isLatestFailing
        onDismiss={noop}
        onOpenDetail={noop}
      />
    )
    expect(screen.getByRole('button', { name: /see suggestion/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /fix 2 related issues/i })).toBeInTheDocument()
  })
})

// Suppress framer-motion warnings in jsdom
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
