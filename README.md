# DevOps AI Agent

**CI/CD failure analysis and auto-remediation — Jenkins-native, human-in-the-loop, runs fully local.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Anthropic](https://img.shields.io/badge/Claude-Haiku%20%2F%20Sonnet-D4A27F?style=flat-square&logo=anthropic&logoColor=white)](https://anthropic.com)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-black?style=flat-square&logo=ollama&logoColor=white)](https://ollama.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

Jenkins pipeline failures are annoying in a specific way — the error is rarely in the obvious place. You end up checking tool configs, credential stores, plugin states, and cache states before you figure out that it was a typo in the tool name all along.

This agent handles that loop. It receives the failure webhook, isolates the failed stage (passing stages are discarded immediately), runs a deterministic crawler against the live Jenkins API to verify tool names, plugins, and credential IDs, then hands roughly 1000 tokens of pre-verified facts to an LLM. Diagnosis and fix buttons appear in the web UI in under 10 seconds.

**90% fewer tokens** than feeding the raw log. **~$0.01/month** in production. Fully local with Ollama if you don't want a cloud API key.

---

## Table of Contents

- [Two Modes](#two-modes)
- [Key Engineering Decisions](#key-engineering-decisions)
- [What It Can and Cannot Fix](#what-it-can-and-cannot-fix)
- [Credential and Secrets Handling](#credential-and-secrets-handling)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Cost](#cost)
- [Developer](#developer)

---

## Two Modes

### Reactive — Failure Analyzer

Triggered automatically when Jenkins sends a failure webhook.

```
Pipeline fails
→ Webhook received by FastAPI server
→ Failed stage isolated — passing stage logs discarded immediately
→ Tool verification crawler queries Jenkins API in parallel with log cleaning
→ LLM receives ~1000 tokens of verified facts (not raw logs)
→ Web UI shows diagnosis + confidence level + fix buttons
→ Human clicks Approve / Retry / Dismiss
→ Fix executes against Jenkins API, result reported back
→ Pipeline re-triggered
```

### Proactive — Copilot

Triggered by chat commands in the web UI.

```
User types: "generate jenkins python-docker-ecr"
→ Relevant base template loaded
→ Template + request sent to generation model (Sonnet / Qwen2.5-Coder)
→ Complete Jenkinsfile returned
→ Preview shown in web UI with syntax highlighting
→ User approves → committed to GitHub / applied to Jenkins via API
```

---

## Key Engineering Decisions

### 1. Selective context feeding

Full pipeline logs are mostly noise. An 8-stage pipeline where stage 5 fails produces 10,000+ tokens — the vast majority from stages that passed. The parser finds the first failing stage and sends only that stage's cleaned logs (~300 tokens) and its Groovy source block (~150 tokens).

Accuracy goes up alongside the cost drop. The model isn't reading thousands of lines of successful output to find what actually broke.

### 2. Deterministic verification before the LLM

Tool configuration checks aren't sent to the LLM as questions. Before any model call, a crawler queries the live Jenkins API and builds a verified facts report. The LLM gets something like "Maven referenced as 'Maven-3.8', configured in Jenkins as 'Maven3', 72% Levenshtein similarity" — not raw error output to interpret.

The model can't hallucinate tool names when we already have the list of what's configured.

### 3. Fix boundaries

Tool name mismatches, missing credentials, inactive plugins, IAM issues — the agent diagnoses these and stops there. No execute button. It gives you the exact details and tells you what to change manually.

Auto-fix covers stateless, reversible operations: retry, cache clear, image pull, timeout increase. Configuration and credentials stay with the human. This isn't a gap to fill later — it's the design.

### 4. Provider abstraction

No model name is hardcoded. Every LLM call goes through a provider factory that reads the task type from `.env`, picks the provider, and falls back to Ollama if the primary is unavailable. The calling code doesn't know what model is on the other end.

Analysis routes to fast, cheap models (Claude Haiku, Llama 3.1 8B). Generation routes to code-quality models (Claude Sonnet, Qwen2.5-Coder 32B). Going from cloud to fully local is two lines in `.env`.

### 5. Credential scrubbing

Every error message, exception string, and log line passes through `scrub()` before it hits a log file or the UI. It matches Anthropic API keys, GitHub PATs, Jenkins tokens (32-char hex), AWS access key IDs, and HTTP Bearer/Basic auth headers, and replaces them with labeled redaction strings.

Jenkins API exceptions are included — those calls frequently echo authentication headers back in error bodies.

---

## What It Can and Cannot Fix

### Auto-fixable (with approval)

| Fix | Trigger condition |
|---|---|
| Retry pipeline | Transient failure, network timeout |
| Clear Docker build cache + retry | Layer cache corruption |
| Pull fresh base image + retry | Stale or wrong image tag |
| Clear npm cache + retry | Node dependency cache corruption |
| Clear pip/Maven cache + retry | Python/Java dependency cache corruption |
| Increase timeout + retry | Pipeline timeout exceeded |
| Patch Jenkinsfile DSL step typo | LLM detects invalid step name, patches file in workspace |
| Configure credential via Jenkins API | LLM identifies missing credential, user provides value in web UI |

### Always diagnostic — never auto-executed

These produce a diagnosis card with exact details and a "Handle manually" button only:

| Issue | Why it's diagnostic-only |
|---|---|
| Tool name mismatch (Jenkinsfile vs Jenkins Global Tool Config) | Requires human decision: rename the tool in Jenkins, or update the Jenkinsfile |
| Missing or inactive plugin | Requires Jenkins admin access and restart |
| Missing credential ID (no value provided) | Agent can't create a credential with no value |
| IAM / permission issues | Security boundary — never auto-modified |
| Runner label mismatch | Infrastructure config, not a pipeline fix |

---

## Credential and Secrets Handling

The agent interacts with three credential systems: Jenkins credentials store, the Anthropic API, and GitHub tokens. Here's how each is handled:

### At runtime

Secret values are accepted only through the web UI credential input — they are passed directly to the Jenkins credentials API in a single request and never stored, logged, or held in memory beyond that call. The audit log records the credential ID, who triggered it, and the timestamp — never the value.

### In error paths

Every error string returned from Jenkins API calls, LLM provider calls, and internal exceptions passes through `scrub()` before it reaches a log file or the UI. Patterns covered:

| Pattern | Redaction label |
|---|---|
| `sk-ant-api03-...` | `[REDACTED:anthropic-key]` |
| `ghp_...` | `[REDACTED:github-token]` |
| `github_pat_...` | `[REDACTED:github-pat]` |
| 32-char lowercase hex | `[REDACTED:jenkins-token]` |
| `AKIA...` | `[REDACTED:aws-key]` |
| `Bearer <token>` | `Bearer [REDACTED]` |
| `Basic <base64>` | `Basic [REDACTED]` |

### In generated pipeline files

When the Copilot generates a Jenkinsfile or GitHub Actions YAML, only variable references appear in the output — never literal values:

```groovy
environment {
    AWS_CREDENTIALS = credentials('aws-prod-credentials')
}
```

### Startup checks

On boot, the agent checks for missing `WEBHOOK_SECRET`, default/weak credentials, and other misconfigurations and logs security warnings before accepting traffic.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Jenkins instance (local Docker or remote) with webhook plugin installed
- API tokens for Jenkins and GitHub

### 1. Clone and configure

```bash
git clone https://github.com/adil-khan-723/devops-ai-agent
cd devops-ai-agent
cp .env.example .env
```

Edit `.env` — minimum required fields:

```env
JENKINS_URL=http://localhost:8080
JENKINS_USER=admin
JENKINS_TOKEN=your_jenkins_api_token

GITHUB_TOKEN=ghp_...
WEBHOOK_SECRET=your_webhook_secret

# Choose provider:
LLM_PROVIDER=ollama          # free, local — or: anthropic
ANTHROPIC_API_KEY=           # required only if LLM_PROVIDER=anthropic
```

### 2. Start

```bash
docker-compose up
```

Or native (no Docker):

```bash
./start.sh
```

`start.sh` handles Docker socket permissions for Jenkins-in-Docker automatically. See [Docker socket section](#docker-socket-access) below.

### 3. Configure Jenkins webhook

In Jenkins → Job → Configure → Post-build actions → HTTP Request:

```
URL:    http://your-agent-host:8000/webhook
Method: POST
```

### 4. Pull local models (optional — skip if using Anthropic)

```bash
ollama pull llama3.1:8b        # ~4.7 GB — analysis
ollama pull qwen2.5-coder:32b  # ~20 GB  — pipeline generation
```

Models stored on external SSD:

```bash
export OLLAMA_MODELS=/Volumes/YourSSD/ollama-models
```

---

## Configuration Reference

Full `.env` reference:

```env
# ── LLM ROUTING ───────────────────────────────────────────────────────────
LLM_PROVIDER=ollama                          # ollama | anthropic
ANALYSIS_MODEL=llama3.1:8b                   # fast model for log analysis
GENERATION_MODEL=qwen2.5-coder:14b           # quality model for generation
LLM_FALLBACK_PROVIDER=ollama                 # fallback if primary unavailable

CONFIDENCE_THRESHOLD=0.75                    # fixes below this are diagnostic-only

# ── OLLAMA ────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODELS=/Volumes/SSD/ollama-models     # optional — path for model storage
OLLAMA_TIMEOUT=120

# ── ANTHROPIC ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=                           # required when LLM_PROVIDER=anthropic
ANTHROPIC_ANALYSIS_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_GENERATION_MODEL=claude-sonnet-4-6

# ── JENKINS ───────────────────────────────────────────────────────────────
JENKINS_URL=http://localhost:8080
JENKINS_USER=admin
JENKINS_TOKEN=                               # Jenkins API token (not password)

# ── GITHUB ────────────────────────────────────────────────────────────────
GITHUB_TOKEN=                                # PAT with repo + secrets scopes
GITHUB_ORG=
GITHUB_DEFAULT_REPO=
GITHUB_REPO=owner/repo                       # active project repo

# ── WEBHOOK SERVER ────────────────────────────────────────────────────────
WEBHOOK_PORT=8000
WEBHOOK_SECRET=                              # shared secret for webhook validation
WEBHOOK_HOST=0.0.0.0

# ── CACHING ───────────────────────────────────────────────────────────────
REDIS_URL=                                   # blank = in-memory fallback

# ── LOGGING ───────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
AUDIT_LOG_PATH=audit.log
```

### Provider switching examples

**Full cloud (Anthropic):**
```env
LLM_PROVIDER=anthropic
ANALYSIS_MODEL=claude-haiku-4-5-20251001
GENERATION_MODEL=claude-sonnet-4-6
```

**Full local (M4 MacBook 32GB):**
```env
LLM_PROVIDER=ollama
ANALYSIS_MODEL=llama3.1:8b
GENERATION_MODEL=qwen2.5-coder:32b
```

---

## Architecture

### Module map

| Module | What it does | Uses LLM? | Key file |
|---|---|---|---|
| `webhook/` | FastAPI server, receives Jenkins failure events | No | `server.py` |
| `parser/` | Identify failed stage, extract + clean logs | No | `pipeline_parser.py`, `log_cleaner.py` |
| `verification/` | Crawl Jenkins API, verify tool names, plugins, credentials | No | `jenkins_crawler.py` |
| `analyzer/` | Build ~1000-token payload, call LLM, cache response | Yes | `context_builder.py`, `llm_client.py` |
| `providers/` | LLM abstraction layer + fallback chain | — | `factory.py`, `base.py` |
| `agent/` | Map failure → fix, confidence check, execute, audit log | No | `fix_executor.py`, `pipeline_fixes.py` |
| `copilot/` | Generate pipelines from templates + NL, commit to GitHub | Yes | `pipeline_generator.py`, `secrets_manager.py` |
| `ui/` | FastAPI routes serving the React web UI | No | `routes.py`, `chat_handler.py` |
| `frontend/` | React + Tailwind web interface | — | `src/components/` |

### System flow — reactive path

```
Pipeline fails (8 stages, stage 5 failed)
│
├── Stages 1–4 logs: discarded immediately
│
└── Stage 5 only →
        │
        ├── [parallel]
        │     ├── Log cleaner
        │     │     Strip ANSI, timestamps, INFO lines
        │     │     Keep ERROR/WARN + 10 lines before first ERROR
        │     │     Output: ~300 tokens
        │     │
        │     └── Jenkins crawler
        │           Parse tools{} block + withCredentials + sh steps
        │           Query Jenkins API: tool names, plugins, credential IDs
        │           Exact match → fuzzy match (Levenshtein ≥ 0.85)
        │           Output: verified facts report, ~200 tokens
        │
        └── Context builder merges:
              Cleaned logs (~300 tok) + Stage source (~150 tok)
              + Verification report (~200 tok) + metadata (~50 tok)
              Total: ~1000 tokens (was 10,000+)
                    │
                    ▼
              LLM Analyzer
              (Haiku or Llama 3.1 8B)
              Returns: what failed, root cause, fix, confidence
                    │
                    ▼
              Web UI card
              Confidence ≥ 0.75 → [Apply Fix] [Retry] [Dismiss]
              Confidence < 0.75 → [Handle Manually]
                    │
              User approves
                    │
                    ▼
              Fix executor → Jenkins API → pipeline re-triggered
              Result posted back to UI card
              All decisions appended to audit.log
```

### Tool name mismatch detection

Jenkins tool name matching is exact. A Jenkinsfile referencing `maven 'Maven-3.8'` fails when Jenkins has `Maven3` configured, and the error message doesn't say that's why.

The crawler finds it:

1. Parse `tools {}` blocks, `withMaven()` calls, and `tool()` steps via regex
2. Query Jenkins `/api/json` for all configured tool names
3. Exact match — if it passes, done
4. No exact match: compute Levenshtein similarity against all configured names
5. Best match below 0.85 is flagged as a mismatch with the closest name surfaced

Credential IDs get the same treatment — every `credentials('ID')` and `credentialsId: 'ID'` reference is checked against the Jenkins credentials store.

### Docker socket access

When Jenkins runs in Docker and Jenkinsfiles use `docker build` / `docker push`, the container needs access to the host Docker daemon via `/var/run/docker.sock`.

`./start.sh` handles this automatically:

| Platform | Method |
|---|---|
| macOS / Windows (Docker Desktop) | `chmod 666` on mounted socket via `docker exec` |
| Linux | Adds `jenkins` user to `docker` group inside container |

**Security note:** `chmod 666` on the Docker socket grants any process on the machine access to the Docker daemon — equivalent to root. Acceptable on a local dev machine, not in shared or production environments. Use Docker-in-Docker or rootless Docker for those.

Manual fix (after every Docker Desktop restart on Mac/Windows):

```bash
docker exec -u root jenkins chmod 666 /var/run/docker.sock
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | ![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white) |
| Webhook server | ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white) + Uvicorn |
| Web UI (frontend) | ![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black) ![Tailwind](https://img.shields.io/badge/Tailwind-3-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white) Framer Motion · Radix UI |
| Cloud LLM | ![Claude](https://img.shields.io/badge/Claude-Haiku%20%2F%20Sonnet-D4A27F?style=flat-square&logo=anthropic&logoColor=white) |
| Local LLM | ![Ollama](https://img.shields.io/badge/Ollama-Llama%203.1%20%2F%20Qwen2.5-black?style=flat-square&logo=ollama&logoColor=white) |
| Containerization | ![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white) |
| Jenkins integration | python-jenkins + httpx → Jenkins REST API |
| GitHub integration | ![GitHub](https://img.shields.io/badge/GitHub-PyGithub-181717?style=flat-square&logo=github&logoColor=white) |
| Caching | ![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white) (in-memory fallback) |
| Config | pydantic-settings + python-dotenv |
| Testing | ![pytest](https://img.shields.io/badge/pytest-135%20tests-0A9EDC?style=flat-square&logo=pytest&logoColor=white) |
| Tool fuzzy matching | python-Levenshtein (threshold 0.85) |

---

## Cost

### Tokens per failure event

| Component | Tokens |
|---|---|
| Cleaned failed-stage logs | ~300 |
| Failed stage Groovy source | ~150 |
| Tool verification report | ~200 |
| Metadata + prompt instructions | ~200 |
| **Total input** | **~850–1000** |
| LLM output | ~400 |

Without stage isolation: 10,000+ tokens per event.

### Cost per analysis call

| Model | Cost |
|---|---|
| Claude Haiku | ~$0.000002 |
| Claude Sonnet | ~$0.000009 |
| Ollama (local) | $0.00 |

### Monthly production estimate

| Activity | Volume | Cost |
|---|---|---|
| Pipeline failure analyses | 200/month @ Haiku | $0.001 |
| Copilot generations | 100/month @ Sonnet | $0.007 |
| **Total** | | **~$0.01/month** |

Response caching (MD5 hash of cleaned logs + stage source + verification report) reduces this further — recurring failures cost zero after the first call.

---

## Developer

**Adil Khan** — DevOps Engineer, HashiCorp Certified Terraform Associate (004)
AWS Cloud Intern @ F13 Technology

[GitHub](https://github.com/adil-khan-723) · [LinkedIn](https://www.linkedin.com/in/adilk3682) · [Dev.to](https://dev.to/adil-khan-723) · adilk81054@gmail.com

