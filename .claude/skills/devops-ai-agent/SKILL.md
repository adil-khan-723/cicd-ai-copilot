---
name: devops-ai-agent
description: >
  Use this skill for ALL tasks on the DevOps AI Agent — a CI/CD Copilot and
  Auto-Remediation System. Trigger for any component, feature, code, architecture,
  or testing question: pipeline failure analysis, tool verification crawler, log cleaning,
  LLM provider abstraction, web UI notifications, fix execution, copilot/pipeline
  generation, secrets management, caching, or writing/running tests. Also triggers for
  scope questions. Prevents Claude from drifting into Kubernetes, APM, or anything
  outside Jenkins and GitHub Actions.
---

# DevOps AI Agent — CI/CD Copilot & Auto-Remediation

**Developer:** Adil Khan | **Stack:** FastAPI, Slack Bolt, Python | **Targets:** Jenkins + GitHub Actions only

## 🔍 Before Writing Any Code — Read Existing Source First

**Always do this at the start of every session:**

1. Run `find . -type f -name "*.py" | head -50` to see what exists
2. Read files relevant to the current task before touching anything
3. Do NOT rewrite or duplicate existing code — build on top of it
4. Continue from where the code left off

---

## ✅ Priority 1 — Pipeline Failure Analysis, Tool Crawler & Notification

These are the core features. Complete and stabilize these before anything else.

### Exact Feature Flow (follow this order strictly)

```
1. Pipeline fails in Jenkins
        ↓
2. Log Parser captures failure — isolate ONLY the failed stage logs + syntax
   Discard all passing stage logs entirely
        ↓
3. Web UI gets notified immediately — failure shown in the already-built UI
        ↓
4. Two things run IN PARALLEL:
   [Log Cleaner] Strip ANSI/timestamps, keep ERRORs + WARNs + 10 lines pre-error
   [Tool Crawler] Deterministically verify tool names, plugins, credentials — NO LLM
        ↓
5. Context Builder merges both outputs into ~850 token payload
        ↓
6. LLM receives the payload — returns: what failed, root cause, fix, confidence level
        ↓
7. Fix proposed in Web UI — user clicks "Apply"
        ↓
8. Fix Executor applies the fix to Jenkins (Jenkinsfile edit or config change)
   Then reruns the Jenkins job automatically
        ↓
9. Result reported back in Web UI
```

### Components

| Component | Responsibility |
|---|---|
| Pipeline Parser | Isolate failed stage logs + syntax; discard passing stages |
| Log Cleaner | Strip ANSI/timestamps; keep ERRORs, WARNs, 10 lines pre-error (~300 tok) |
| Tool Verifier Crawler | Deterministic: tool names, plugins, credentials, secrets, runners — NO LLM |
| Context Builder | Merge cleaned logs + syntax + verification → ~850 token payload |
| LLM Analyzer | Returns: what failed, root cause, fix suggestion, confidence (High/Med/Low) |
| Web UI Notifier | Show failure + proposed fix in UI; "Apply" button triggers fix executor |
| Fix Executor | Apply fix to Jenkins → rerun job → report result in UI |

**Tool Verifier — Jenkins:** parse `tools{}` block → query Jenkins API → exact + fuzzy name match → verify plugin active → verify credentials exist.

**Tool Verifier — GitHub Actions:** parse workflow YAML → check secrets exist → check runner labels → check action versions.

**Fix Executor never handles:** plugin install, tool install, credential creation — always manual.

**Confidence gate:** Only `high` confidence shows Apply button. Medium/Low = analysis only, no apply button.

---

## ✅ Priority 2 — Pipeline Generation (Copilot Mode)

Build after Priority 1 is fully working and tested.

### Flow
`User types request in UI/Slack → generate Jenkinsfile or GHA YAML → preview shown → user approves → commit to GitHub or apply to Jenkins via API`

| Component | Responsibility |
|---|---|
| Pipeline Generator | Generate Jenkinsfile (Groovy) or GHA YAML from natural language |
| Slack/UI Copilot Handler | Intake, preview display, handle change requests |
| Repo Committer | Commit generated file to GitHub via API |
| Jenkins Configurator | Apply pipeline to Jenkins via API |

**Model:** `claude-sonnet-4-6` for generation tasks.

---

## ✅ Priority 3 — Supporting Systems

Add after both above are working.

| Component | Responsibility |
|---|---|
| Secrets Manager | Jenkins credential + GitHub secrets management |
| Provider Factory | Abstraction over Anthropic, Ollama, Groq, Gemini; fallback chain |
| Response Cache | Hash(logs + verification) → cached result; TTL 3600s |
| Audit Logger | Immutable log of every action |
| Docker Compose | Full local stack |

---

## 🧪 Testing — Fully Automated with pytest

**Framework:** pytest + pytest-mock (fake Jenkins/Slack/UI calls — no real connections needed)

**Rule:** After implementing any component, write its tests immediately. Do not move to the next component until tests pass.

### Test Flow (mirrors the feature flow exactly)

```
Test 1 — Pipeline Parser
  - Feed a fake multi-stage Jenkins log with stage 3 failing
  - Assert: only stage 3 logs returned, stages 1-2 discarded

Test 2 — Log Cleaner
  - Feed raw log with ANSI codes, timestamps, passing lines
  - Assert: clean output, only ERRORs + WARNs + 10 pre-error lines kept

Test 3 — Tool Verifier Crawler
  - Mock Jenkins API response with configured tools
  - Feed a Jenkinsfile referencing a slightly wrong tool name
  - Assert: mismatch detected, fuzzy suggestion returned, no LLM called

Test 4 — Context Builder
  - Feed cleaned log + tool verification report
  - Assert: merged payload is ≤850 tokens

Test 5 — LLM Analyzer
  - Mock LLM response (no real API call)
  - Assert: structured output has what/why/fix/confidence fields

Test 6 — Web UI Notification
  - Simulate a failure event
  - Assert: UI receives the failure data and displays it correctly

Test 7 — Full Flow Integration
  - Simulate pipeline failure end-to-end (all mocked)
  - Assert: failure → notification → fix proposed → apply clicked → Jenkins rerun triggered
```

### If a Test Fails — Claude Must:
1. Print exactly which assertion failed and why
2. Show the actual value vs expected value
3. Identify which component is broken
4. Suggest the specific fix with code
5. Never just say "test failed" — always give full context

### Test File Structure
```
tests/
├── test_pipeline_parser.py
├── test_log_cleaner.py
├── test_tool_crawler.py
├── test_context_builder.py
├── test_llm_analyzer.py
├── test_ui_notifier.py
└── test_integration_flow.py
```

### Running Tests
```bash
pytest tests/ -v --tb=short
```
Always run with `-v` so output is clear. If any test fails, stop and fix before continuing.

---

## Core Design Rules

1. **Selective Context** — Feed ONLY failed stage logs + syntax (~850 tokens). Never full logs.
2. **Deterministic First** — Crawler runs before LLM. LLM gets verified facts.
3. **Human-in-the-Loop** — Nothing executes without user clicking Apply in UI. Tool/credential issues = manual only.
4. **Provider Agnostic** — No model hardcoded. All LLM calls via provider factory. `.env` only.
5. **Confidence Gate** — Only `high` confidence shows Apply button.
6. **Parallel Processing** — Log cleaning + tool verification always run together.

---

## Model Routing

| Task | Model |
|---|---|
| Log analysis, fix suggestion, verification summary | `claude-haiku-4-5-20251001` |
| Pipeline generation | `claude-sonnet-4-6` |
| Local/free alternative | `ollama/llama3.1:8b` or `qwen2.5-coder:32b` |

---
