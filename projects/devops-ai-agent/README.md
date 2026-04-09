# DevOps AI Agent — CI/CD Copilot & Auto-Remediation System

**Status:** Active — Phase 1 (Foundation)
**Started:** 2026-04-09

## Description
AI-powered agent that monitors CI/CD pipelines (Jenkins + GitHub Actions), analyzes failures with LLMs, suggests fixes, and executes remediations with human-in-the-loop Slack approval. Also generates Jenkinsfiles and GitHub Actions workflows from natural language.

## Key Dates
- Build Phase 1 target: Foundation complete, pipeline failure → Slack analysis working
- Publication target: End of Q2 2026 (GitHub + Dev.to + LinkedIn)

## Source of Truth
Full architecture, component breakdown, and `.env.example` are in `README.md` at repo root.

## Build Phases
1. Foundation (webhook + parser + log cleaner + Slack notifier)
2. Tool Verification Crawler (Jenkins + GH Actions API crawlers)
3. Approval Flow + Fix Execution (Slack buttons + audit log + caching)
4. Copilot Mode (pipeline generation from natural language)
5. Secrets Management + Polish (full stack Docker Compose)
6. Documentation + Publication

## Notes
- Scope is strictly CI/CD. K8s monitoring is a separate project.
- Secrets accepted via Slack DM only, never logged, sent directly to Jenkins/GitHub API.
- All LLM routing is env-driven — switch from Claude to Ollama via `.env` change only.
