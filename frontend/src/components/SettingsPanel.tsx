import { Settings, Server, GitBranch, Brain, Webhook, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface SettingSection {
  icon: React.ElementType
  title: string
  desc: string
  items: { label: string; value: string }[]
}

const SECTIONS: SettingSection[] = [
  {
    icon: Server,
    title: 'Jenkins',
    desc: 'Build server connection',
    items: [
      { label: 'Endpoint', value: 'Configured in .env' },
      { label: 'Webhook', value: 'POST /webhook/jenkins-notification' },
      { label: 'Setup', value: './start.sh --setup-jenkins' },
    ],
  },
  {
    icon: GitBranch,
    title: 'GitHub',
    desc: 'Repository integration',
    items: [
      { label: 'Token', value: 'Configured in .env' },
      { label: 'Commits', value: 'Via GitHub API' },
    ],
  },
  {
    icon: Brain,
    title: 'LLM Provider',
    desc: 'Analysis and generation model',
    items: [
      { label: 'Analysis', value: 'claude-haiku / llama3.1:8b' },
      { label: 'Generation', value: 'claude-sonnet / qwen2.5-coder' },
      { label: 'Switch', value: 'LLM_PROVIDER in .env' },
    ],
  },
  {
    icon: Webhook,
    title: 'Webhooks',
    desc: 'Event endpoints',
    items: [
      { label: 'Jenkins', value: 'POST /webhook/jenkins-notification' },
      { label: 'Pipeline Failure', value: 'POST /webhook/pipeline-failure' },
      { label: 'SSE Stream', value: 'GET /api/stream' },
    ],
  },
]

export function SettingsPanel({ onOpenSetup }: { onOpenSetup: () => void }) {
  return (
    <div className="h-full overflow-y-auto bg-bg">
      <div className="max-w-2xl mx-auto px-8 py-10">

        {/* Header */}
        <div className="mb-8">
          <h2 className="text-[22px] font-extrabold text-text-primary tracking-tight">Configuration</h2>
          <p className="text-[13px] font-mono text-text-muted mt-2 leading-relaxed">
            Credentials and integrations are managed in{' '}
            <code className="font-mono text-accent bg-accent-dim border border-accent-border rounded-md px-1.5 py-0.5 text-[12px]">.env</code>
            {'. '}Use the setup wizard to update connection settings.
          </p>
        </div>

        {/* Setup CTA */}
        <div className="rounded-2xl border border-accent-border bg-gradient-to-r from-overlay to-card-hi px-5 py-5 flex items-center justify-between mb-8 shadow-soft">
          <div>
            <p className="text-[15px] font-bold text-text-primary tracking-tight">Project Setup Wizard</p>
            <p className="text-[12px] font-mono text-text-muted mt-1">
              Update Jenkins URL, GitHub token, or LLM credentials
            </p>
          </div>
          <Button
            size="sm"
            onClick={onOpenSetup}
            className="gap-2 bg-gradient-accent hover:opacity-90 text-white font-semibold border-0 text-[13px] h-9 px-4 font-mono rounded-xl shadow-soft"
          >
            <Settings className="h-3.5 w-3.5" strokeWidth={2} />
            Open Wizard
          </Button>
        </div>

        {/* Sections */}
        <div className="space-y-4">
          {SECTIONS.map(({ icon: Icon, title, desc, items }) => (
            <div
              key={title}
              className="rounded-2xl border border-accent-border/50 bg-white overflow-hidden shadow-card"
            >
              {/* Section header */}
              <div className="flex items-center gap-3 px-5 py-4 border-b border-accent-border/30 bg-overlay/30">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white border border-accent-border/50">
                  <Icon className="h-4 w-4 text-accent" strokeWidth={1.75} />
                </div>
                <div>
                  <p className="text-[14px] font-bold text-text-primary leading-none">{title}</p>
                  <p className="text-[11px] font-mono text-text-muted mt-1 leading-none">{desc}</p>
                </div>
              </div>
              {/* Rows */}
              <div className="divide-y divide-accent-border/20">
                {items.map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between px-5 py-3.5 hover:bg-overlay/20 transition-colors">
                    <span className="text-[12px] font-mono text-text-muted">{label}</span>
                    <span className="text-[12px] font-mono text-text-base text-right max-w-[55%] truncate">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-accent-border/30 flex items-center gap-6">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-[12px] font-mono text-text-muted hover:text-accent transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
            API Docs
          </a>
          <a
            href="http://localhost:8000/webhook/test"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-[12px] font-mono text-text-muted hover:text-accent transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
            Test Webhook
          </a>
        </div>
      </div>
    </div>
  )
}
