# Work & Business

## Current Position
AWS Cloud Intern @ F13 Technology (active)

## Primary Project: DevOps AI Agent — CI/CD Copilot & Auto-Remediation System

An AI-powered agent that monitors CI/CD pipelines (Jenkins + GitHub Actions), analyzes failures using local or cloud LLMs, suggests fixes, executes remediations with human-in-the-loop approval via Slack, and generates pipelines from natural language.

**Scope:** Strictly CI/CD — Jenkins and GitHub Actions only. Kubernetes, cluster monitoring, and APM are explicitly out of scope (separate project).

### Core Design Principles
1. **Selective context feeding** — Only failed stage logs sent to LLM (~850 tokens vs 10,000+, 90% reduction)
2. **Deterministic before LLM** — Tool verification via API crawlers, LLM receives facts not raw logs
3. **Human-in-the-loop always** — No fix executes without Slack button approval
4. **Provider agnostic** — All LLM calls via abstraction layer, swap models via `.env`

### Two Operating Modes
- **Reactive** — Pipeline fails → webhook → analyze → Slack alert with approve/reject
- **Proactive (Copilot)** — Slack command → generate Jenkinsfile or GH Actions YAML → preview → approve → commit

### Tech Stack
- Python 3.11+, FastAPI (webhook server), Slack Bolt SDK
- LLMs: Claude Haiku/Sonnet (Anthropic), Ollama (Llama 3.1 8B, Qwen2.5-Coder 32B, Mistral 7B), Groq, Gemini
- Jenkins API (python-jenkins), GitHub API (PyGithub)
- Docker + Docker Compose, Redis (optional cache)

### Model Routing
- Analysis tasks → `claude-haiku-4-5-20251001` or `llama3.1:8b` (fast, cheap)
- Generation tasks → `claude-sonnet-4-6` or `qwen2.5-coder:32b` (quality critical)
- All routes env-driven, zero hardcoding

### Cost Profile
~$0.01/month in production. Dev/testing phase covered by Anthropic free credits (~$0.015 total). Caching reduces repeat failures by 60-70%.

### Fix Capabilities
**Auto-fixable (with approval):** Retry pipeline, clear Docker/npm/pip/maven cache, pull fresh image, increase timeout
**Never auto-fixed:** Tool name mismatches, missing plugins, missing credentials, missing secrets, IAM issues — always diagnostic alert only

### What Makes It Different (Interview Points)
- Deterministic tool-name mismatch detection before LLM (eliminates hallucination category)
- 90% token reduction via failed-stage isolation
- Full local operation possible (Qwen2.5-Coder 32B on M4 MacBook)
- Response caching by MD5 hash of context

## Resume Line
"Built an AI-powered CI/CD Copilot using local and cloud LLMs (Ollama/Llama 3.1, Qwen2.5-Coder 32B, Claude Haiku/Sonnet) with a deterministic tool-verification crawler that cross-checks Jenkins Global Tool Configuration and GitHub Actions secrets against pipeline definitions before LLM analysis — achieving 90% token reduction through selective context feeding, human-in-the-loop approval via Slack, automated fix execution, and a Copilot mode for generating Jenkinsfiles and GitHub Actions workflows from natural language."

## Publication Plan
- Dev.to article: "Building a Human-in-the-Loop AI Agent for CI/CD Failure Recovery"
- LinkedIn post with architecture walkthrough
