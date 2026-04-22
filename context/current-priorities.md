# Current Priorities

Last updated: 2026-04-22

## Active Build Phase
**Phase 1 — Foundation** is the starting point.

## 6-Phase Build Plan

### Phase 1 — Foundation
- FastAPI webhook server receives pipeline failure events
- Pipeline parser identifies failed stage
- Log extractor pulls only failed stage logs
- Log cleaner strips noise (ANSI, timestamps, INFO lines)
- Basic Ollama integration for local testing (free)
- Web UI notifier displays formatted analysis
- No fix execution yet — observation mode only

**Milestone:** Pipeline fails → clean analysis shown in web UI

### Phase 2 — Tool Verification Crawler
- Jenkins crawler: parse Jenkinsfile tool refs, query Jenkins API, exact + fuzzy match
- GitHub Actions crawler: parse workflow YAML, query GitHub API for secrets/runners
- Context builder merges logs + verification report (~850 tokens total)
- Confidence threshold implementation

**Milestone:** Tool mismatches detected precisely before LLM call

### Phase 3 — Approval Flow & Fix Execution
- Web UI approval handler (buttons: Approve / Retry / Dismiss)
- Audit log (append-only)
- Fix executor for pipeline-level fixes
- Pipeline rerun after fix
- Response caching (MD5 hash key)
- Fallback chain (configured provider → Ollama → UI alert)

**Milestone:** User approves fixes via web UI, agent executes and reports result

### Phase 4 — Copilot Mode
- Pipeline generator: Jenkins Groovy + GitHub Actions YAML
- Base templates for common patterns
- Web UI chat command handler
- Repo committer via GitHub API
- Jenkins configurator via API

**Milestone:** Generate complete pipelines from natural language in the web UI

### Phase 5 — Secrets Management & Polish
- Secrets manager (web UI only, never logged, direct to Jenkins/GitHub API)
- Full multi-provider LLM wiring + fallback chain tested
- Docker Compose full stack

**Milestone:** Full system running end to end locally

### Phase 6 — Documentation & Publication
- Comprehensive README with architecture diagram
- Test coverage for core components
- GitHub repo cleanup
- Dev.to article + LinkedIn post

**Milestone:** Published, documented, live on GitHub
