# DevOps AI Agent — Full Build Plan
# From Zero to Published: Every Increment

**Project:** CI/CD Copilot & Auto-Remediation System  
**Hardware:** M4 MacBook Air, 32GB, 256GB internal + 2TB Crucial external SSD  
**LLM Strategy:** Local-first (Ollama) → Cloud API via `.env` swap, zero code changes  
**Models locked:** `llama3.1:8b` (analysis) + `qwen2.5-coder:14b` (generation)  
**Architecture source of truth:** `README.md`

---

## How to Read This Plan

Each increment = one focused, shippable unit of work.  
Complete one → verify it works → move to next.  
Never skip verification steps — they catch issues before they compound.

---

## PRE-PHASE: Environment & Tooling From Scratch

### Increment 1 — Project Scaffold
**What:** Create the full directory structure and dependency files  
**Deliverables:**
- `requirements.txt` with all dependencies pinned
- `.env.example` with every variable documented
- `.gitignore` (Python, `.env`, `.tmp/`, `__pycache__`, models)
- `docker-compose.yml` stub (fills out in Phase 5)
- All module directories created with empty `__init__.py`: `providers/`, `parser/`, `verification/`, `analyzer/`, `agent/`, `copilot/`, `web_ui/`, `webhook/`, `config/`, `templates/`, `tests/`

**Verify:** `python -m pytest tests/` exits 0 (no tests yet, just confirms structure)

---

### Increment 2 — Config & Environment Loader
**What:** Centralized settings management that reads `.env` and validates required vars  
**Files:**
- `config/settings.py` — Pydantic Settings class, loads all `.env` vars, validates on startup
- `config/__init__.py` — exports `get_settings()`

**Key vars to load:**
```
LLM_PROVIDER=ollama
ANALYSIS_MODEL=llama3.1:8b
GENERATION_MODEL=qwen2.5-coder:14b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODELS=/Volumes/SSD/ollama-models
CONFIDENCE_THRESHOLD=0.75
```

**Verify:** `python -c "from config import get_settings; print(get_settings())"` prints config without errors

---

### Increment 3 — Ollama Local Setup
**What:** Install Ollama, configure external SSD storage, pull both models  
**Steps (documented as a runbook, not code):**
1. `brew install ollama`
2. `launchctl setenv OLLAMA_MODELS /Volumes/SSD/ollama-models`
3. Edit `~/Library/LaunchAgents/com.ollama.ollama.plist` to persist env var
4. `ollama pull llama3.1:8b`
5. `ollama pull qwen2.5-coder:14b`
6. `ollama list` — confirm both models present

**Verify:** `curl http://localhost:11434/api/tags` returns both models in JSON

**Runbook saved to:** `docs/setup/ollama-setup.md`

---

### Increment 4 — LLM Provider Abstraction Layer
**What:** Base class + factory + Ollama provider. Full plug-and-play from day one.  
**Files:**
- `providers/base.py` — `BaseLLMProvider` abstract class with `complete(prompt, system) -> str` and `is_available() -> bool`
- `providers/ollama_provider.py` — Ollama implementation using `httpx`, handles connection errors
- `providers/factory.py` — `get_provider(task: str) -> BaseLLMProvider` reads `LLM_PROVIDER` + task-specific model from settings
- `providers/__init__.py` — exports `get_provider`

**Task routing (from `.env`):**
```
# analysis tasks → ANALYSIS_MODEL
# generation tasks → GENERATION_MODEL
```

**Verify:** 
```python
from providers import get_provider
p = get_provider("analysis")
print(p.complete("Say hello", "You are helpful"))
```
Returns a real response from Ollama

---

### Increment 5 — Web UI Setup
**What:** Configure the web UI for local development  
**Steps (runbook):**
1. Confirm `web_ui/` directory exists with `app.py` and templates
2. Start Flask app: `python -m web_ui.app`
3. Open browser at `http://localhost:5000`
4. Verify notification panel and approval buttons render

**Verify:** Web UI loads at `http://localhost:5000` without errors

---

## PHASE 1: Foundation — Observe & Notify

### Increment 6 — FastAPI Webhook Server
**What:** Receives pipeline failure events, validates webhook secret, returns 200  
**Files:**
- `webhook/server.py` — FastAPI app, `POST /webhook/pipeline-failure` endpoint
- `webhook/validators.py` — HMAC signature validation for Jenkins + GitHub webhook secrets

**Payload accepted:** Jenkins webhook JSON or GitHub Actions workflow_run event  
**On receipt:** validate signature → log event → return `{"status": "received"}`

**Verify:** 
```bash
uvicorn webhook.server:app --reload
curl -X POST http://localhost:8000/webhook/pipeline-failure \
  -H "Content-Type: application/json" \
  -d '{"job_name": "test-pipeline", "build_number": 42, "result": "FAILURE"}'
```
Returns `{"status": "received"}`

---

### Increment 7 — Pipeline Parser
**What:** Identifies failed stage from webhook payload  
**Files:**
- `parser/pipeline_parser.py` — `parse_failure(payload: dict) -> FailureContext`
- `parser/models.py` — `FailureContext` dataclass: job_name, build_number, failed_stage, platform (jenkins/github)

**Logic:**
- Jenkins: extract `failedStage` from payload or build log header
- GitHub Actions: extract failed job/step name from `workflow_run` event

**Verify:** Unit test with fixture payloads for Jenkins + GitHub → correct `FailureContext` returned

---

### Increment 8 — Log Extractor
**What:** Pulls only the failed stage logs — discards everything else  
**Files:**
- `parser/log_extractor.py` — `extract_failed_logs(context: FailureContext, raw_log: str) -> str`

**Logic:**
- Scan log for stage start/end markers
- Return only the block containing the failed stage
- Hard cap: 2000 chars max (trimmed from end if exceeded)

**Verify:** Test with a 500-line Jenkins log — returns only the 40-line failed stage block

---

### Increment 9 — Log Cleaner
**What:** Strips noise from extracted logs  
**Files:**
- `parser/log_cleaner.py` — `clean_log(raw: str) -> str`

**Strips:**
- ANSI escape codes (`\x1b[...m`)
- Timestamps (`[2024-01-15 14:23:11]`, `14:23:11`)
- `[INFO]`, `[DEBUG]`, `[Pipeline]` prefixes
- Blank lines (3+ consecutive → 1)
- Jenkins progress bars (`#####...`)

**Verify:** Input 300-char noisy log → output is clean, readable, under 200 chars

---

### Increment 10 — Basic Web UI Notifier
**What:** Posts a formatted failure alert to the web UI (no buttons yet, no LLM yet)  
**Files:**
- `web_ui/notifier.py` — `send_failure_alert(context: FailureContext, cleaned_log: str)`
- `web_ui/message_templates.py` — HTML/JSON builder for failure message

**Message format:**
```
🔴 Pipeline Failure: build-api #42
Stage: Docker Build
[cleaned log excerpt — first 300 chars]
Analysis pending...
```

**Verify:** Trigger with test payload → message appears in web UI notification panel

---

### Increment 11 — Phase 1 Integration Test
**What:** Wire everything together end-to-end, no LLM yet  
**Full flow:** Webhook receives event → parse → extract logs → clean → web UI message  

**Files:**
- `tests/test_phase1_integration.py` — sends test webhook, asserts web UI notification sent (mocked)

**Verify:** `pytest tests/test_phase1_integration.py -v` passes  
**Milestone achieved:** Pipeline fails → clean alert in web UI ✓

---

## PHASE 2: Tool Verification & LLM Analysis

### Increment 12 — Jenkins Tool Verification Crawler
**What:** Parses Jenkinsfile tool references, queries Jenkins API, flags mismatches  
**Files:**
- `verification/jenkins_crawler.py` — `verify_jenkins_tools(jenkinsfile_path: str, jenkins_url: str) -> VerificationReport`

**Logic:**
1. Parse `tools {}` block from Jenkinsfile (regex)
2. Query `jenkins_url/api/json` for configured global tools
3. Exact match first → fuzzy match (Levenshtein ratio > 0.85) if no exact
4. Check plugin status via Jenkins Plugin Manager API
5. Check credential IDs exist via Jenkins Credentials API

**Output:** `VerificationReport` with: matched, mismatched, missing plugins, missing credentials

**Verify:** Unit test with sample Jenkinsfile + mocked Jenkins API response → correct mismatch detected

---

### Increment 13 — GitHub Actions Verification Crawler
**What:** Parses workflow YAML, verifies secrets + runners configured  
**Files:**
- `verification/actions_crawler.py` — `verify_actions_config(workflow_path: str, github_repo: str) -> VerificationReport`

**Logic:**
1. Parse workflow YAML (PyYAML)
2. Extract all `${{ secrets.X }}` references
3. Query GitHub API for configured repo/org secrets
4. Verify runner labels exist (GitHub-hosted or self-hosted)
5. Check action versions (warn on `@main` or unpinned)

**Verify:** Unit test with sample workflow YAML + mocked GitHub API → missing secret flagged

---

### Increment 14 — Context Builder (850-Token Budget)
**What:** Merges cleaned log + verification report into LLM-ready payload  
**Files:**
- `analyzer/context_builder.py` — `build_context(log: str, report: VerificationReport, context: FailureContext) -> str`

**Token budget allocation:**
- System prompt: ~100 tokens (static)
- Pipeline metadata: ~50 tokens
- Verification findings: ~150 tokens
- Cleaned log: ~550 tokens (trimmed if needed)
- Total: ~850 tokens

**Verify:** `len(tokenize(build_context(...)))` stays under 900 tokens across all test cases

---

### Increment 15 — LLM Analyzer
**What:** Sends context to Ollama, parses structured response  
**Files:**
- `analyzer/prompt_builder.py` — builds system + user prompt
- `analyzer/llm_client.py` — `analyze(context: str) -> AnalysisResult`
- `analyzer/response_parser.py` — extracts: root_cause, fix_suggestion, confidence (0.0-1.0), fix_type
- `analyzer/cache.py` — MD5 hash of context → cached response (in-memory, Redis optional)

**Prompt instructs LLM to return JSON:**
```json
{
  "root_cause": "...",
  "fix_suggestion": "...",
  "confidence": 0.87,
  "fix_type": "clear_cache|retry|pull_image|increase_timeout|diagnostic_only"
}
```

**Verify:** Send real cleaned log to Ollama → valid JSON response parsed correctly

---

### Increment 16 — Enhanced Web UI Notification with Analysis
**What:** Update notifier to include verification results + LLM analysis  
**Files:** Update `web_ui/notifier.py` + `web_ui/message_templates.py`

**Message format:**
```
🔴 Pipeline Failure: build-api #42
Stage: Docker Build

🔍 Tool Verification
  ✗ Tool mismatch: 'docker' → configured as 'Docker'
  ✗ Missing credential: ECR_CREDENTIALS

🤖 Analysis (87% confidence)
  Root cause: Docker tool name mismatch in global config
  Suggested fix: Rename tool in Jenkins Global Tool Config

[buttons appear in next increment]
```

**Verify:** Full message renders correctly in web UI with all sections

---

## PHASE 3: Approval Flow & Fix Execution

### Increment 17 — Web UI Approval Handler
**What:** Handle button clicks — Approve / Retry / Dismiss  
**Files:**
- `web_ui/approval_handler.py` — web UI action handlers
- Update `web_ui/message_templates.py` — add buttons based on confidence threshold

**Button logic:**
- Confidence ≥ 0.75 → show [Apply Fix] + [Dismiss]
- Confidence < 0.75 → show [Manual Review] + [Dismiss]
- Diagnostic-only fix types → no [Apply Fix] button, ever

**Verify:** Click [Apply Fix] in web UI → handler logs "fix approved" + updates message to "Processing..."

---

### Increment 18 — Fix Executor
**What:** Executes approved fixes against Jenkins/GitHub APIs  
**Files:**
- `agent/fix_executor.py` — `execute_fix(fix_type: str, context: FailureContext) -> FixResult`
- `agent/fix_mapper.py` — maps `fix_type` → executor function
- `agent/pipeline_fixes.py` — concrete fix implementations:
  - `retry_pipeline(job, build)` via python-jenkins
  - `clear_docker_cache(job)` — build with cache-bust parameter
  - `clear_npm_cache(job)` — same pattern
  - `pull_fresh_image(job, image)` — trigger image pull job
  - `increase_timeout(job, current_timeout)` — update job config XML

**Never auto-fixed (return diagnostic only):** tool mismatches, missing plugins, missing credentials, IAM issues

**Verify:** Mock Jenkins API → retry fix triggered → job requeued

---

### Increment 19 — Audit Log
**What:** Append-only record of every fix execution  
**Files:**
- `agent/audit_log.py` — `log_fix(fix_type, triggered_by, job, result, timestamp)`

**Format:** JSONL (one JSON object per line, append-only)  
**Fields:** timestamp, fix_type, job_name, build_number, triggered_by (web UI user), result (success/failed), confidence_at_trigger  
**Never logged:** secret values, credentials, tokens

**Verify:** Execute a fix → `audit.log` has correct entry → second fix appends (not overwrites)

---

### Increment 20 — Response Cache + Fallback Chain
**What:** Cache LLM responses, add fallback when provider unavailable  
**Files:**
- Update `analyzer/cache.py` — add TTL (1 hour default), hit/miss logging
- Update `providers/factory.py` — add fallback chain logic

**Fallback order (from `.env` config):**
1. Configured primary provider (e.g., `ollama`)
2. If unavailable → try secondary (e.g., `anthropic`)
3. If all fail → send web UI alert: "LLM unavailable, manual review required"

**Verify:** 
- Same log twice → second call returns from cache (no Ollama API call made)
- Kill Ollama → fallback triggers → web UI alert sent

---

### Increment 21 — Phase 3 Integration Test
**What:** Full reactive flow end-to-end test  
**Flow:** Webhook → parse → extract → clean → verify → build context → LLM → web UI alert → button click → execute fix → audit log entry  

**Verify:** `pytest tests/test_phase3_integration.py -v` passes  
**Milestone achieved:** Approve fix via web UI → agent executes → reports result ✓

---

## PHASE 4: Copilot Mode

### Increment 22 — Pipeline Templates
**What:** Base templates for common pipeline patterns  
**Files in `templates/`:**
- `jenkins/python-docker-ecr.groovy` — Python build → Docker → push to ECR
- `jenkins/node-docker.groovy` — Node.js build → Docker
- `jenkins/generic.groovy` — Minimal base template
- `github/python-ci.yml` — Python test + lint + build
- `github/docker-ecr.yml` — Docker build + ECR push
- `github/generic.yml` — Minimal base

**Verify:** Each template is valid Groovy/YAML that Jenkins/GitHub would accept

---

### Increment 23 — Jenkins Pipeline Generator
**What:** NL description → Jenkinsfile via LLM + templates  
**Files:**
- `copilot/pipeline_generator.py` — `generate_jenkinsfile(nl_request: str) -> str`

**Logic:**
1. Select closest base template based on keywords in NL request
2. Build prompt: system (pipeline expert) + template + NL request
3. Call `get_provider("generation")` → `qwen2.5-coder:14b`
4. Parse LLM output → validate it's valid Groovy (basic syntax check)
5. Return generated Jenkinsfile string

**Verify:** `generate_jenkinsfile("Python app, Docker build, push to ECR")` → valid Jenkinsfile

---

### Increment 24 — GitHub Actions Generator
**What:** NL description → workflow YAML via LLM + templates  
**Files:**
- `copilot/actions_generator.py` — `generate_workflow(nl_request: str) -> str`

**Logic:** Same as Increment 23 but for YAML output  
**Validation:** Parse output with PyYAML — if invalid, retry once with correction prompt

**Verify:** `generate_workflow("Node.js app, run tests, build Docker, deploy to EC2")` → valid YAML

---

### Increment 25 — Web UI Command Handler
**What:** `generate <type> <description>` web UI command  
**Files:**
- `web_ui/copilot_handler.py` — handles generate commands from web UI

**Commands:**
- `generate jenkins <description>` → Jenkins pipeline
- `generate github <description>` → GitHub Actions workflow
- `generate jenkins list` → show available templates

**Flow:** Command received → "Generating..." indicator → call generator → post preview

**Verify:** `generate jenkins python docker ecr` in web UI → pipeline preview posted

---

### Increment 26 — Pipeline Preview + Copilot Approval Flow
**What:** Show generated pipeline in web UI with Approve / Edit / Cancel buttons  
**Files:**
- Update `web_ui/message_templates.py` — copilot preview message
- Update `web_ui/copilot_handler.py` — approval action handlers

**Preview message:**
```
📋 Generated Jenkinsfile — python-docker-ecr
[code block — first 20 lines]
[View Full File] [Approve & Commit] [Cancel]
```

**Verify:** Preview renders with buttons, Approve button triggers next step

---

### Increment 27 — Repo Committer
**What:** Commits generated pipeline file to GitHub repo  
**Files:**
- `copilot/repo_committer.py` — `commit_file(repo: str, path: str, content: str, message: str)`

**Logic:**
1. Use PyGithub to get/create file at `path` in `repo`
2. Commit with message: "feat: add generated pipeline [bot]"
3. Return commit URL

**Verify:** Approve in web UI → file appears in GitHub repo at correct path with correct content

---

### Increment 28 — Jenkins Configurator
**What:** Applies pipeline config to Jenkins via API  
**Files:**
- `copilot/jenkins_configurator.py` — `create_job(name: str, jenkinsfile_content: str)`

**Logic:** Use python-jenkins to create/update job with generated Jenkinsfile  
**Verify:** Approve in web UI → new Jenkins job appears with correct pipeline config

---

## PHASE 5: Secrets, Cloud LLMs & Production Polish

### Increment 29 — Secrets Manager
**What:** Handle secrets via web UI only, pass directly to API, never log  
**Files:**
- `copilot/secrets_manager.py` — `request_secret(user_id: str, secret_name: str) -> str`

**Rules (hardcoded, non-negotiable):**
- Only ever entered via web UI — never exposed in logs or shared views
- Passed directly to Jenkins/GitHub API
- Never stored (not in memory, not in files, not in audit log)
- Audit log records: secret name + user + timestamp (never value)

**Verify:** Code review — grep entire codebase for secret variable logging, assert zero hits

---

### Increment 30 — Cloud LLM Providers
**What:** Wire up Claude — all via `.env` switch  
**Files:**
- `providers/anthropic_provider.py` — Claude Haiku (analysis) + Sonnet (generation)

**Update `providers/factory.py`:** recognize new provider names from `LLM_PROVIDER` env var

**Verify:** Set `LLM_PROVIDER=anthropic` in `.env` → same analysis flow works with zero code changes

---

### Increment 31 — Docker Compose Full Stack
**What:** One command to run everything  
**Files:**
- `Dockerfile` — Python 3.11 slim, installs requirements, runs webhook server
- `docker-compose.yml` — services: `webhook`, `web-ui`, `redis` (optional cache)
- `.env.example` — updated with Docker-specific vars

**Verify:** `docker-compose up` → webhook server running on port 8000, web UI accessible

---

### Increment 32 — Multi-Provider End-to-End Test
**What:** Verify plug-and-play works for all providers  
**Test matrix:**
- Ollama (local) → analysis + generation ✓
- Anthropic → analysis + generation ✓
- Fallback chain: kill primary → secondary activates ✓

**Verify:** `pytest tests/test_providers.py -v` — all provider tests pass

---

## PHASE 6: Documentation & Publication

### Increment 33 — Test Suite
**What:** Core test coverage for all critical paths  
**Test files:**
- `tests/test_parser.py` — log extraction + cleaning
- `tests/test_verification.py` — Jenkins + GitHub crawlers (mocked APIs)
- `tests/test_analyzer.py` — context building, token budget
- `tests/test_agent.py` — fix mapping, audit log
- `tests/test_copilot.py` — generation, template selection
- `tests/test_providers.py` — all providers + fallback chain

**Target:** 80%+ coverage on core modules  
**Verify:** `pytest tests/ --cov=. --cov-report=term` passes with coverage report

---

### Increment 34 — Architecture Diagram
**What:** Visual diagram for README and Dev.to article  
**Tool:** Mermaid (renders in GitHub README)

**Diagrams:**
- Reactive flow (8-stage pipeline with parallel verification)
- Copilot flow (NL → generate → approve → commit)
- Provider abstraction layer
- Module dependency graph

**Saved to:** `docs/diagrams/`

---

### Increment 35 — README Polish & GitHub Release
**What:** Final README pass, repo cleanup, GitHub release  
**Steps:**
- Embed Mermaid diagrams in README
- Add badges: Python version, license, test status
- Ensure `.env.example` is complete and accurate
- Tag `v1.0.0` release on GitHub
- Write GitHub release notes

**Verify:** Fresh clone → follow README → system running in under 30 minutes

---

### Increment 36 — Dev.to Article
**What:** Technical article for publication  
**Title:** "Building a Human-in-the-Loop AI Agent for CI/CD Failure Recovery"  
**Sections:**
1. The problem (CI/CD failures cost hours weekly)
2. Architecture overview (diagram)
3. The 90% token reduction trick (selective context feeding)
4. Deterministic verification before LLM (no hallucinations on tool config)
5. Provider abstraction + local LLM setup (Ollama on M4)
6. Human-in-the-loop approval (why this matters)
7. What I'd do differently

**Saved as draft to:** `docs/articles/devto-draft.md`

---

### Increment 37 — LinkedIn Post
**What:** LinkedIn announcement post  
**Format:** Short (300 words), architecture screenshot, GitHub link  
**Saved as draft to:** `docs/articles/linkedin-draft.md`

---

## Summary: 37 Increments Across 7 Sections

| Section | Increments | Milestone |
|---|---|---|
| Pre-Phase (Environment) | 1–5 | Dev environment fully configured, web UI + Ollama live |
| Phase 1 (Foundation) | 6–11 | Pipeline fails → web UI alert ✓ |
| Phase 2 (Verification + LLM) | 12–16 | Tool mismatches detected, LLM analysis in web UI ✓ |
| Phase 3 (Approval + Execution) | 17–21 | Approve fix via web UI → agent executes ✓ |
| Phase 4 (Copilot Mode) | 22–28 | NL → Jenkinsfile/YAML → committed to GitHub ✓ |
| Phase 5 (Cloud + Polish) | 29–32 | Full stack, all providers, Docker Compose ✓ |
| Phase 6 (Docs + Publish) | 33–37 | Live on GitHub, Dev.to + LinkedIn published ✓ |

---

## LLM Provider `.env` Reference

```bash
# Switch any time — zero code changes
LLM_PROVIDER=ollama              # local-first (start here)
# LLM_PROVIDER=anthropic         # Claude Haiku/Sonnet

ANALYSIS_MODEL=llama3.1:8b
GENERATION_MODEL=qwen2.5-coder:14b

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODELS=/Volumes/SSD/ollama-models  # external SSD

# Cloud providers (add keys when needed)
ANTHROPIC_API_KEY=
```

---

## Critical Rules (Non-Negotiable Throughout)

1. Failed stage logs only → LLM. Passing stage logs discarded immediately.
2. Tool verification always runs before LLM analysis.
3. No fix executes without web UI button approval.
4. Tool mismatches, missing credentials, missing plugins → diagnostic alert only, never auto-fixed.
5. Secrets: web UI only, direct to API, never logged anywhere.
6. Every increment verified before moving to next.
