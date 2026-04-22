# How the Project Works — End to End

---

## Starting the App

Run `./launch.sh` or `./start.sh` (or `docker-compose up`). The script:
1. Checks Python 3.11+, creates `.venv`, installs `requirements.txt`
2. Copies `.env.example` → `.env` if missing, exits asking you to fill it
3. Checks Ollama reachability or API key depending on `LLM_PROVIDER`
4. Checks Jenkins URL and GitHub token
5. Builds the React frontend
6. Launches `uvicorn webhook.server:app` on port 8000

FastAPI starts with a **lifespan** hook that:
- Calls `validate_config(settings)` — exits immediately with clear error if provider key missing
- Starts a background Jenkins health monitor polling `/api/json` every 10 seconds
- Publishes `jenkins_status` SSE events when connection state changes

---

## What the User Sees (Web UI)

Browser hits `http://localhost:8000`. React app loads. Four panels:

| Panel | What it does |
|---|---|
| **Pipeline Feed** | Live stream of failure cards as they arrive |
| **Chat** | Streaming copilot — generate pipelines from natural language |
| **Jobs Browser** | Lists all Jenkins jobs, shows status, lets you trigger manually |
| **Settings** | Enter Jenkins URL/credentials, save to `.env` live |

First-time user sees a **Setup Wizard** — enter Jenkins URL, username, API token → saved to `.env` and settings cache cleared.

The browser opens a persistent **SSE connection** to `/events`. On connect, it replays the last 200 events from an in-memory ring buffer (so you don't miss anything from before the page loaded), then streams live events as they arrive.

---

## A Pipeline Fails — The Reactive Flow

### Step 1 — Jenkins POSTs to the webhook

Jenkins is configured to POST to `http://your-server:8000/webhook/jenkins-notification` when a build finishes. Payload contains: job name, build number, phase (`FINALIZED`), status (`FAILURE`/`ABORTED`/`UNSTABLE`), and the console log URL.

The endpoint returns `200` immediately and processes in a background thread so Jenkins isn't kept waiting.

---

### Step 2 — Parser

`parser.pipeline_parser.parse_failure(payload)` builds a `FailureContext`:

```
job_name, build_number, failed_stage, platform,
raw_log, branch, repo, pipeline_stages (list of name+status)
```

Stage detection uses regex on the log — looks for `[Pipeline] { (StageName)` blocks. Finds where errors are concentrated. If nothing obvious, takes second-to-last stage. Also detects GitHub Actions payloads (uses `##[group]` markers instead).

---

### Step 3 — Log Extraction + Cleaning

`log_extractor` pulls ONLY the failed stage block from the full log. Discards all passing stages entirely. Takes last 2000 characters (errors are at the end).

`log_cleaner` strips: ANSI color codes, timestamps, log level prefixes (`[INFO]`, `[DEBUG]`), progress bars, duplicate blank lines. What's left is pure error text.

This is the **90% token reduction** — instead of sending 10,000+ token full logs to the LLM, you send ~550 tokens of clean error text.

---

### Step 4 — Tool Verification (Deterministic, Pre-LLM)

`verification.jenkins_crawler` does this before touching any LLM:

- Parses the Jenkinsfile for tool references: `tools { maven 'Maven3'; jdk 'JDK11' }` and credential references: `credentials('MY_TOKEN')`
- Hits Jenkins APIs: `/api/json?depth=2` for configured tools, `/pluginManager/api/json` for installed plugins, `/credentials/store/system/domain/_/api/json` for credential IDs
- Does **exact match first**, then **Levenshtein fuzzy match** (threshold 0.85) — catches `Maven3` vs `maven3` mismatches
- Returns a `VerificationReport`: matched tools, mismatched tools with similarity scores, missing plugins, missing credentials

This step **never blocks** — if Jenkins API is unreachable it returns an empty report and moves on. But when it works, it eliminates an entire category of LLM hallucination: tool name errors are detected deterministically, not guessed.

---

### Step 5 — Context Building

`analyzer.context_builder.build_context()` merges everything into a single markdown prompt under **850 tokens total**:

- 50 tokens: metadata (platform, job, build, stage, branch)
- 150 tokens: verification report (only if issues found)
- 550 tokens: cleaned log (trimmed with binary search if needed, appends `[...truncated]`)

Uses `tiktoken` (cl100k_base) for accurate token counting.

---

### Step 6 — LLM Analysis

`analyzer.llm_client.analyze(context)`:

1. **Cache check first** — MD5 hash of context string → in-memory cache (1-hour TTL). Same error on same job returns instantly, no API cost.
2. **Provider selection** — `get_provider("analysis")` checks primary provider is available, falls back to fallback provider if not.
3. **Calls LLM** with system prompt ("You are expert DevOps engineer, respond JSON only") + user prompt (the 850-token context).
4. **Parses response** — strips markdown fences if present, validates JSON, coerces types. If `confidence < 0.6` → forces `fix_type = diagnostic_only` regardless of what LLM said.
5. **Caches result**.

LLM response schema:
```json
{
  "root_cause": "Maven tool 'Maven3' not found in Jenkins Global Tool Config",
  "fix_suggestion": "Add Maven installation named 'Maven3' in Manage Jenkins → Global Tool Configuration",
  "confidence": 0.92,
  "fix_type": "diagnostic_only"
}
```

Fix types: `retry` | `clear_cache` | `pull_image` | `increase_timeout` | `diagnostic_only`

---

### Step 7 — SSE Event Published

`analysis_complete` event fires into the `EventBus`. All connected browsers receive it instantly. The event contains: full analysis, verification data, pipeline stages, log excerpt, confidence score, fix type.

---

### Step 8 — UI Renders Failure Card

Browser receives `analysis_complete` → React renders a **BuildCard** in the Pipeline Feed showing:
- Job name, build number, failed stage
- Root cause (from LLM)
- Fix suggestion
- Confidence score
- Pipeline stage list (which passed, which failed)
- "View full logs" button → opens drawer with full console output
- Fix action buttons (Retry / Clear Cache / etc.) — only shown if `fix_type != diagnostic_only`

---

### Step 9 — User Approves Fix

User clicks a fix button → browser POSTs to `/api/fix` with `{fix_type, job_name, build_number}`.

`agent.fix_executor.execute_fix()` routes to the right function:

| fix_type | What happens |
|---|---|
| `retry` | `jenkins.build_job(job_name)` |
| `clear_cache` | `build_job(..., parameters={"DOCKER_NO_CACHE": "true"})` — falls back to plain retry if no params |
| `pull_image` | `build_job(..., parameters={"PULL_FRESH_IMAGE": "true"})` |
| `increase_timeout` | Fetches job XML config, finds `<timeout>NNN</timeout>`, doubles it, reconfigures job |
| `diagnostic_only` | **Never executes** — returns immediately |

Every fix execution is written to `audit.log` (append-only JSONL): timestamp, fix_type, job, build, triggered_by, result, confidence.

---

### Step 10 — Build Recovers (or Fails Again)

Jenkins runs the new build. If it **succeeds**: POST to `/webhook/jenkins-notification` with status `SUCCESS` → server finds the previous `analysis_complete` event in history → publishes `build_success` event → UI shows recovery message on the original card.

If it **fails again**: full pipeline restarts from Step 1.

---

## The Copilot Flow (Proactive Mode)

User goes to Chat panel, types: _"Generate a Python CI pipeline for Jenkins with Docker build and ECR push"_

`/api/chat` streams a response:

1. `chat_handler` keeps last 8 conversation turns, calls generation provider (Sonnet or qwen2.5-coder — quality model, not speed model)
2. `copilot.template_selector` keyword-matches the request → picks closest base template (python-docker-ecr, node-docker, generic, etc.)
3. `copilot.pipeline_generator` sends template + user request to LLM with system prompt instructing Groovy syntax
4. Validates output: starts with `pipeline {`, balanced braces, has `stages`, has `stage(` — retries with correction prompt if invalid
5. Streams result back to chat as typed text

If user says "commit this" → `copilot.jenkins_configurator` creates or updates the Jenkins job via XML API using `CpsFlowDefinition` (pipeline script). Or `copilot.github_committer` commits the YAML file to the repo via PyGithub.

---

## LLM Provider System

Two task types, two model tiers:

| Task | Default model | Why |
|---|---|---|
| Analysis (failures) | `llama3.1:8b` / `claude-haiku-4-5-20251001` | Fast, cheap — 850 tokens in, JSON out |
| Generation (pipelines) | `qwen2.5-coder:14b` / `claude-sonnet-4-6` | Quality critical — code must be valid |

Provider factory tries primary → fallback. If both fail → `ProviderUnavailableError` → analysis returns `diagnostic_only` with error message, never crashes the app.

---

## Safety Rules (Hard-Coded, Never Bypassed)

1. `diagnostic_only` fix type → code never calls Jenkins API, full stop
2. Tool name mismatches, missing credentials, missing plugins → always `diagnostic_only`, LLM cannot override
3. `confidence < 0.6` → forced to `diagnostic_only` regardless of LLM's `fix_type`
4. No fix runs without explicit user click in UI — human-in-the-loop always
5. Secrets never logged, never in SSE events, handled in-memory only

---

## Complete Data Flow (Summary)

```
Jenkins build FAILURE
    ↓
POST /webhook/jenkins-notification
    ↓
parse_failure() → FailureContext
    ↓
extract_failed_logs() → isolated stage log
    ↓
clean_log() → cleaned text
    ↓
verify_jenkins_tools() → VerificationReport
    ↓
build_context() → markdown prompt (≤850 tokens)
    ↓
analyze() → cache check → LLM call → parse → cache result
    ↓
publish analysis_complete → EventBus → SSE → browser
    ↓
UI renders BuildCard with fix options
    ↓
User clicks fix button
    ↓
POST /api/fix → execute_fix() → Jenkins API
    ↓
log_fix() → audit.log
    ↓
publish fix_result → UI updates card
    ↓
Jenkins reruns → SUCCESS
    ↓
publish build_success → UI shows recovery
```
