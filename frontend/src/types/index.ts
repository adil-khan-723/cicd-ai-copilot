export type StepStatus = 'done' | 'running' | 'failed' | 'pending'

export interface StepEvent {
  type: 'step'
  job: string
  build: string | number
  stage: string
  detail: string
  status: StepStatus
  fix_type?: string
  confidence?: number
}

export interface AnalysisCompleteEvent {
  type: 'analysis_complete'
  job: string
  build: string | number
  failed_stage: string
  root_cause: string
  fix_suggestion: string
  fix_type: string
  confidence: number
  log_excerpt: string
}

export interface FixResultEvent {
  type: 'fix_result'
  job: string
  build: string | number
  fix_type: string
  success: boolean
  detail: string
}

export type SSEEvent = StepEvent | AnalysisCompleteEvent | FixResultEvent

export interface BuildCard {
  key: string
  job: string
  build: string | number
  steps: StepEvent[]
  analysis?: AnalysisCompleteEvent
  fixResult?: FixResultEvent
  dismissed: boolean
  createdAt: number
}

export interface JenkinsJob {
  name: string
  url: string
  color: string
  status: string
}

export interface SetupFormData {
  github_repo: string
  github_token: string
  jenkins_url: string
  jenkins_user: string
  jenkins_token: string
}

export type ActivePanel = 'pipeline' | 'chat' | 'jobs' | 'settings'

// Chat
export interface ChatHistoryEntry {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatMessage extends ChatHistoryEntry {
  id: string
  pipeline?: string
  pipelinePlatform?: 'jenkins' | 'github'
  committed?: boolean
  isStreaming?: boolean
}
