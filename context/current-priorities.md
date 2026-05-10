# Current Priorities

Last updated: 2026-05-10

## Active Build Phase
**Phase 5 complete → Phase 6 (docs + publish)**

## Recent Shipped (2026-04 → 2026-05)
- Multi-profile Jenkins management with idempotent re-add (PR #49)
- Multi-key API manager with per-analysis tracking (PR #50)
- Styled Select component replacing native dropdowns (PR #51)
- Jenkins failure poller as fallback for unreliable Notification Plugin (PR #52)
- One-click Jenkins auto-setup: installs notification + junit plugins, configures all jobs (PR #53)
- Anthropic provider hot-reload for API key changes without restart (PR #48)
- Model dropdowns (locked to known IDs) replacing free-text fields (PR #45)
- Test Connection button in setup wizard with unsaved creds (PR #44)
- Auth-method format validation (token vs password warnings) (PR #47)
- Validator soft-warns instead of SystemExit when API key missing (PR #46)
- Auto-run Jenkins setup in background on profile activate (this PR)

## GH Actions
Explicitly out of scope until post-publication. Skip all GHA items in every phase.

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
- ~~GitHub Actions crawler~~ — skipped (post-publication)
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

### Phase 4 — Copilot Mode ✅ COMPLETE
- Pipeline generator: Jenkins Groovy ~~+ GitHub Actions YAML~~ — GHA skipped
- Base templates for common patterns (Jenkins only)
- Web UI chat command handler
- ~~Repo committer via GitHub API~~ — GHA skipped
- Jenkins configurator via API

**Milestone:** ✅ Generate complete pipelines from natural language in the web UI

### Phase 5 — Secrets Management & Polish ✅ COMPLETE
- Secrets manager (web UI only, never logged, direct to Jenkins/GitHub API)
- Multi-key API manager with active-key tracking + per-analysis attribution
- Auto Jenkins setup (notification plugin + junit + per-job config)
- Failure poller as fallback when notification plugin fails
- Hot-reload settings (no restart needed for key/model changes)
- Provider hot-reload (API key changes flow through without server bounce)
- Full multi-provider LLM wiring + fallback chain tested
- Docker Compose full stack
- Cross-OS launch script (macOS / Ubuntu / AlmaLinux / cloud VMs via Lima)

**Milestone:** ✅ Full system running end to end locally + on cloud VM

### Phase 6 — Documentation & Publication
- Comprehensive README with architecture diagram
- Test coverage for core components
- GitHub repo cleanup
- Dev.to article + LinkedIn post

**Milestone:** Published, documented, live on GitHub
