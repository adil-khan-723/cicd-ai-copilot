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

export interface PipelineStage {
  name: string
  status: 'passed' | 'failed' | 'skipped'
}

export interface VerificationToolMismatch {
  referenced: string
  configured: string
  match_score: number
}

export interface VerificationData {
  matched_tools: string[]
  mismatched_tools: VerificationToolMismatch[]
  missing_plugins: string[]
  missing_credentials: string[]
  missing_secrets: string[]
  missing_runners: string[]
  unpinned_actions: string[]
  errors: string[]
}

export interface AnalysisCompleteEvent {
  type: 'analysis_complete'
  job: string
  build: string | number
  failed_stage: string
  root_cause: string
  fix_suggestion: string
  steps: string[]
  fix_type: string
  confidence: number
  log_excerpt: string
  pipeline_stages: PipelineStage[]
  verification?: VerificationData
  bad_step?: string
  correct_step?: string
  bad_image?: string
  correct_image?: string
  credential_type?: string
}

export interface FixResultEvent {
  type: 'fix_result'
  job: string
  build: string | number
  fix_type: string
  success: boolean
  detail: string
  next_build?: number
}

export interface BuildSuccessEvent {
  type: 'build_success'
  job: string
  build: string | number
  previous_failed_build?: string | number
  previous_root_cause?: string
}

export interface JenkinsStatusEvent {
  type: 'jenkins_status'
  ok: boolean
}

export type SSEEvent = StepEvent | AnalysisCompleteEvent | FixResultEvent | BuildSuccessEvent | JenkinsStatusEvent

export interface BuildCard {
  key: string
  job: string
  build: string | number
  steps: StepEvent[]
  analysis?: AnalysisCompleteEvent
  fixResult?: FixResultEvent
  dismissed: boolean
  createdAt: number
  successEvent?: BuildSuccessEvent
}

export interface JenkinsJob {
  name: string
  url: string
  color: string
  status: string
}

export interface SetupFormData {
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
