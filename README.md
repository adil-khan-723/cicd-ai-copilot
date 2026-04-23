# DevOps AI Agent — CI/CD Copilot & Auto-Remediation System

> An AI-powered DevOps agent that monitors CI/CD pipelines, analyzes failures using local or cloud LLMs, suggests fixes, executes remediations with human-in-the-loop approval via the web UI, and acts as a copilot for generating pipelines and managing secrets — purely focused on CI/CD (Jenkins and GitHub Actions).

---

## Table of Contents

- [Project Overview](#project-overview)
- [Core Philosophy](#core-philosophy)
- [Scope — What This Project Is and Is Not](#scope)
- [Two Modes of Operation](#two-modes-of-operation)
- [Complete System Flow](#complete-system-flow)
- [Architecture Decisions & Optimizations](#architecture-decisions--optimizations)
- [The Tool Verification Crawler — Deep Dive](#the-tool-verification-crawler--deep-dive)
- [Full Tech Stack](#full-tech-stack)
- [Project Structure](#project-structure)
- [Component Breakdown](#component-breakdown)
- [LLM Provider System](#llm-provider-system)
- [Model Routing Strategy](#model-routing-strategy)
- [Local Model Recommendations](#local-model-recommendations)
- [Cost Analysis](#cost-analysis)
- [Fix Capabilities](#fix-capabilities)
- [Copilot Capabilities](#copilot-capabilities)
- [Web UI Interface](#web-ui-interface)
- [Security Design](#security-design)
- [Configuration Reference](#configuration-reference)
- [Build Phases & Timeline](#build-phases--timeline)
- [Resume Value](#resume-value)

---

## Project Overview

This project is a production-grade AI DevOps agent built by Adil Khan as a portfolio and real-world tool.

**What it solves:**
Every DevOps team deals with CI/CD pipeline failures, misconfigured tools, wrong tool references in pipeline files, missing credentials, and repetitive infrastructure setup. This agent automates failure analysis, suggests precise fixes, executes remediations safely with human approval, and helps generate pipelines through natural language — all through the web UI.

**What makes it different from tutorials:**
- Not a toy — solves real problems production teams face daily
- Human-in-the-loop design — AI never acts without approval
- Selective context feeding — optimized for minimal LLM token usage
- Deterministic tool verification — LLM receives facts, not guesses
- Fully configurable LLM backend — swap models via config, zero code changes
- Caching layer — repeated failures cost zero tokens
- Self-hosted LLM support — runs completely free with Ollama

---

## Core Philosophy

### 1. Selective Context Feeding
Do NOT feed the entire pipeline log to the LLM. A pipeline with 8 stages where stages 1-4 pass and stage 5 fails should only send the failed stage logs plus that stage's syntax to the LLM. Passing stage logs are noise — they inflate token costs and reduce analysis accuracy. This alone achieves a 90% token reduction.

### 2. Deterministic Before LLM
Tool verification — is Maven configured? does the tool name in the Jenkinsfile match what Jenkins has? is the plugin installed? are credentials present? — is handled by a deterministic crawler agent, NOT the LLM. The LLM receives verified facts. This prevents hallucination on tool configuration questions entirely.

### 3. Human-in-the-Loop
The agent NEVER executes fixes automatically. Every fix requires explicit manual approval via web UI buttons. This is intentional — AI should not have unchecked access to production infrastructure. This pattern is called Human-in-the-Loop and it is how production AI systems are built responsibly.

### 4. Provider Agnostic
No model is hardcoded anywhere. Every LLM call goes through a provider abstraction layer. Switching from Claude to Ollama requires only a .env change — zero code changes. This makes the project work completely free on local models.

### 5. Confidence Thresholds
Fix execution only proceeds if the LLM returns a confidence level above a configured threshold. Low confidence responses show the analysis but do not offer an execute button — only a manual review option.

### 6. Parallel Processing
Tool verification and log cleaning run in parallel — not sequentially. This reduces total response time significantly.

---

## Scope

### What this project IS:
- A CI/CD failure analyzer and auto-remediation agent
- Focused purely on Jenkins pipelines and GitHub Actions workflows
- A tool configuration verifier for Jenkins Global Tool Configuration and GitHub Actions setup
- A copilot for generating Jenkinsfiles and GitHub Actions YAML
- A secrets and credentials manager for Jenkins and GitHub

### What this project is NOT:
- A Kubernetes monitoring or management tool — K8s is a separate project
- A cluster health monitor
- An application performance monitor
- Anything outside the CI/CD pipeline scope

Any pipeline-triggered deployment steps (like rolling back a K8s deployment that a pipeline kicked off) are in scope. Cluster monitoring, Alertmanager events, and pod health are out of scope and belong to a separate dedicated project.

---

## Two Modes of Operation

### Mode 1 — Reactive (Failure Analyzer)
Triggered automatically when a pipeline fails.

```
Pipeline fails
→ Logs captured
→ Failed stage identified and isolated
→ Tool verification crawler runs in parallel with log cleaning
→ LLM analyzes merged context
→ web UI notification with fix suggestion
→ Manual approval
→ Fix executed
→ Result reported back to web UI
```

### Mode 2 — Proactive (Copilot)
Triggered by user commands in the web UI.

```
User types natural language request
→ Agent generates Jenkinsfile or GitHub Actions YAML
→ Preview shown in web UI
→ User approves or requests changes
→ Committed to GitHub repo or applied to Jenkins via API
```

---

## Complete System Flow

### Reactive Flow — Failure Analysis

```
Pipeline with 8 stages:
Stages 1-4: PASS ✅  →  Ignored entirely, logs discarded
Stage 5:    FAIL ❌
            ↓
┌─────────────────────────────────────────┐
│           Pipeline Parser               │
│  - Identifies which stage failed        │
│  - Extracts ONLY failed stage logs      │
│  - Extracts failed stage syntax         │
│  - Notes tool references in that stage  │
└──────────────┬──────────────────────────┘
               ↓
   ┌───────────────────────────┐
   │   Two parallel processes  │
   └───────────────────────────┘
        ↙                 ↘
┌─────────────┐    ┌──────────────────────────┐
│ Log Cleaner │    │  Tool Verifier Crawler   │
│             │    │                          │
│ Strip ANSI  │    │  For Jenkins:            │
│ Strip times │    │  - Parse Jenkinsfile     │
│ Keep ERROR  │    │    tools{} block         │
│ Keep WARN   │    │  - Query Jenkins API     │
│ Keep 10     │    │    for configured tools  │
│ lines before│    │  - Cross-check names     │
│ first ERROR │    │    exact match check     │
│             │    │  - Fuzzy match on miss   │
│             │    │  - Check plugin active   │
│             │    │  - Check binary path     │
│             │    │  - Check credentials     │
│             │    │                          │
│             │    │  For GitHub Actions:     │
│             │    │  - Parse workflow YAML   │
│             │    │  - Check secrets exist   │
│             │    │  - Check runner labels   │
│             │    │  - Check env variables   │
│             │    │  - Check action versions │
│             │    │                          │
│             │    │  Returns verified facts  │
│             │    │  NO LLM involved here    │
└──────┬──────┘    └────────────┬─────────────┘
       └──────────┬─────────────┘
                  ↓
┌─────────────────────────────────────────┐
│           Context Builder               │
│                                         │
│  Merges into single optimized payload:  │
│  - Cleaned failed stage logs (~300 tok) │
│  - Failed stage pipeline syntax (~200)  │
│  - Tool verification report (~200 tok)  │
│                                         │
│  Total: ~850 tokens (not 10,000+)       │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│             LLM Analyzer                │
│                                         │
│  Model: Claude Haiku or Llama 3.1 8B    │
│  (configurable via .env)                │
│                                         │
│  Returns:                               │
│  - What failed (specific)               │
│  - Why it failed (root cause)           │
│  - Suggested fix (actionable)           │
│  - Confidence level: High / Med / Low   │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│           Web UI Notifier               │
│                                         │
│  Formatted message with:                │
│  - What failed                          │
│  - Tool verification results            │
│  - Root cause                           │
│  - Suggested fix                        │
│  - Confidence level                     │
│                                         │
│  If confidence HIGH:                    │
│  [✅ Apply Fix] [🔁 Retry] [❌ Dismiss] │
│                                         │
│  If confidence LOW or MED:              │
│  [📋 I'll Handle This Manually]         │
└──────────────────┬──────────────────────┘
                   ↓
           User clicks button
                   ↓
┌─────────────────────────────────────────┐
│          Approval Handler               │
│                                         │
│  If Approved:                           │
│  → Decision logged to audit log         │
│  → Fix Executor runs specific fix       │
│  → Pipeline reruns                      │
│  → Result reported back to web UI       │
│                                         │
│  If Rejected or Manual:                 │
│  → Decision logged to audit log         │
│  → Team notified to handle manually     │
│                                         │
│  Audit log always records:              │
│  - Who approved or rejected             │
│  - Timestamp                            │
│  - What fix was proposed                │
│  - What was executed                    │
│  - Result of execution                  │
└─────────────────────────────────────────┘
```

### Proactive Flow — Copilot

```
User in web UI:
"generate jenkins python-docker-ecr"
         ↓
Copilot Handler receives command
         ↓
Pipeline Generator:
  - Loads relevant base template
  - Sends template + user request to LLM
  - Model: Claude Sonnet or Qwen2.5-Coder 32B
  - LLM fills template intelligently
  - Returns complete Jenkinsfile or YAML
         ↓
Web UI preview with syntax highlighting
         ↓
[✅ Commit to Repo] [✏️ Modify] [❌ Cancel]
         ↓
If approved:
→ Repo Committer pushes to GitHub
→ OR Jenkins Configurator applies via API
→ Confirmation shown in web UI with file path
```

---

## Architecture Decisions & Optimizations

### Token Optimization — 90% Reduction
A full 8-stage pipeline can generate 10,000+ tokens of logs. By parsing the result first and extracting only the failed stage, the context sent to the LLM drops to approximately 850 tokens. This is the single most impactful optimization in the project.

### Deterministic Verification First
Tool configuration checks are intentionally done without the LLM. A crawler queries the Jenkins API or GitHub API and returns verified facts. The LLM then has accurate information instead of having to infer it from error messages — which leads to hallucination.

### The Tool Name Mismatch Problem
One of the most common and most frustrating CI/CD failures is a tool name mismatch. In Jenkins you configure a tool globally under Manage Jenkins → Global Tool Configuration. You give it a name like "Maven3". Then in your Jenkinsfile you write:

```groovy
tools {
    maven 'Maven-3.8'
}
```

The pipeline fails because "Maven-3.8" does not match "Maven3". The error message is often misleading and time-consuming to debug. The crawler catches this by parsing the Jenkinsfile tools{} block, querying the Jenkins API for all configured tool names, running exact match comparison, and if no match is found running a fuzzy similarity check to suggest the likely intended tool name. Same problem exists in GitHub Actions where secrets or runner labels are referenced but not configured.

### Response Caching
Identical failure signatures use cached LLM responses. Cache key is MD5 hash of cleaned logs + stage syntax + verification report. If the same Docker permission error appears 10 times in a month, the LLM is called once and the other 9 are served from cache at zero cost.

### Log Cleaning Pipeline
Before sending logs to the LLM:
1. Strip ANSI color escape codes
2. Strip timestamps
3. Remove all INFO level lines
4. Keep ERROR and WARN lines
5. Keep 10 lines before the first ERROR for context
6. Strip duplicate whitespace and blank lines

### Fallback Chain
```
Configured provider unavailable?
→ Try Ollama local
→ Ollama also unavailable?
→ Post to web UI: manual review required
→ Never silently fail
→ Always notify
```

---

## The Tool Verification Crawler — Deep Dive

This is one of the most original and valuable components in the project. It runs deterministically before any LLM call and returns a verified facts report. No guessing, no inference — only what the APIs confirm.

### Jenkins Tool Verification

**What it checks:**

Step 1 — Parse the Jenkinsfile or pipeline definition:
- tools{} block references: maven, jdk, nodejs, git, docker, etc.
- sh steps that invoke tools: mvn, npm, java, docker, gradle, etc.
- withCredentials blocks: credential IDs referenced
- environment blocks: variables referenced

Step 2 — Query Jenkins REST API:
- GET /api/json for installed plugins and their active status
- GET /computer/api/json for agent/node tool installations
- GET /credentials/store/system/api/json for configured credential IDs
- Global Tool Configuration endpoint for configured tool names

Step 3 — Cross-check and verify:
- Does the tool name in the Jenkinsfile exactly match a configured tool name?
- If not, run fuzzy match to find closest configured name and suggest it
- Is the plugin that manages this tool installed and active?
- Is the tool binary path valid on the agent?
- Are all credential IDs referenced in the pipeline present in the credentials store?

**Example verification report:**

```
Jenkins Tool Verification Report:
─────────────────────────────────
Maven:
  Referenced in Jenkinsfile as:  'Maven-3.8'
  Configured in Jenkins:          NOT FOUND ❌
  Available configurations:       'maven-3.6', 'Maven3'
  Best match suggestion:          'Maven3' (72% similarity)
  Likely cause:                   Name mismatch

JDK:
  Referenced as:  'JDK-17'
  Configured:     'JDK-17' ✅
  Path valid:     ✅

Docker:
  Plugin:   'docker-plugin' installed and active ✅
  Daemon:   Running ✅
  Registry: 'docker-registry-credentials' ✅

AWS Credentials:
  Referenced ID:  'aws-prod-credentials'
  In store:       ✅
```

### GitHub Actions Tool Verification

**What it checks:**

Step 1 — Parse the workflow YAML:
- All uses: fields (action names and versions)
- All ${{ secrets.NAME }} references
- All env: variable references
- All runs-on: runner label requests

Step 2 — Query GitHub API:
- GET /repos/owner/repo/actions/secrets for configured secrets
- GET /repos/owner/repo/actions/runners for available runners and labels
- Check action versions against known releases

Step 3 — Cross-check:
- Is every referenced secret configured in repo or org settings?
- Does a runner with the requested label exist and is it online?
- Is the action version valid?

**Example verification report:**

```
GitHub Actions Verification Report:
────────────────────────────────────
Secrets:
  AWS_ACCESS_KEY_ID:      Configured ✅
  AWS_SECRET_ACCESS_KEY:  Configured ✅
  DOCKER_PASSWORD:        NOT FOUND ❌

Runner:
  Requested: 'self-hosted, linux, x64'
  Available: 'self-hosted, linux, x64' ✅ (2 runners online)

Actions:
  actions/checkout@v4:          Valid ✅
  actions/setup-java@v3:        Valid ✅
  aws-actions/amazon-ecr-login: No version pinned ⚠️
```

---

## Full Tech Stack

| Layer | Technology |
|---|---|
| CI/CD Integration | Jenkins + GitHub Actions |
| Local LLM | Ollama (Llama 3.1 8B, Qwen2.5-Coder 32B, Mistral 7B) |
| Cloud LLM | Claude API (Haiku 3.5 + Sonnet 4.5) |
| Language | Python 3.11+ |
| Webhook Server | FastAPI |
| Jenkins API | python-jenkins |
| GitHub API | PyGithub |
| Containerization | Docker + Docker Compose |
| Caching | In-memory (Redis optional for production) |
| Config Management | python-dotenv |
| Log Processing | Python regex + custom parser |

---

## Project Structure

```
devops-ai-agent/
│
├── providers/                           # LLM Provider abstraction layer
│   ├── __init__.py
│   ├── base.py                          # Abstract interface all providers implement
│   ├── factory.py                       # Router + fallback logic
│   ├── anthropic_provider.py            # Claude Haiku / Sonnet
│   ├── ollama_provider.py               # Local Llama / Qwen / Mistral
│
├── parser/                              # Pipeline result parsing — NO LLM
│   ├── __init__.py
│   ├── pipeline_parser.py               # Identifies passed vs failed stages
│   ├── log_extractor.py                 # Extracts ONLY failed stage logs
│   └── log_cleaner.py                   # Strips noise, timestamps, ANSI codes
│
├── verification/                        # Deterministic tool verification — NO LLM
│   ├── __init__.py
│   ├── tool_verifier.py                 # Main orchestrator — runs checks in parallel
│   ├── jenkins_crawler.py               # Parses Jenkinsfile + queries Jenkins API
│   │                                    # Checks tools{} block vs Global Tool Config
│   │                                    # Exact + fuzzy name matching
│   │                                    # Plugin active status
│   │                                    # Credential ID verification
│   ├── actions_crawler.py               # Parses workflow YAML + queries GitHub API
│   │                                    # Checks secrets configured in repo/org
│   │                                    # Checks runner labels exist and online
│   │                                    # Checks action versions
│   │                                    # Checks env variables defined
│   ├── docker_checker.py                # Checks Docker daemon, registry, permissions
│   └── credentials_checker.py           # Cross-checks credentials across systems
│
├── analyzer/                            # LLM-based analysis
│   ├── __init__.py
│   ├── context_builder.py               # Merges logs + verification report
│   ├── prompt_builder.py                # Builds structured prompts per task type
│   ├── llm_client.py                    # Calls provider factory, handles retries
│   ├── response_parser.py               # Parses LLM response into structured data
│   └── cache.py                         # MD5-based response cache
│
├── agent/                               # Fix execution engine
│   ├── __init__.py
│   ├── fix_executor.py                  # Main orchestrator, confidence checks
│   ├── fix_mapper.py                    # Maps failure type to appropriate fix
│   ├── pipeline_fixes.py                # Pipeline fixes (retry, cache clear, etc.)
│   └── audit_log.py                     # Append-only log of all decisions
│
├── copilot/                             # Proactive generation features
│   ├── __init__.py
│   ├── pipeline_generator.py            # Generates Jenkinsfile Groovy pipelines
│   ├── actions_generator.py             # Generates GitHub Actions YAML workflows
│   ├── secrets_manager.py               # Writes secrets to Jenkins/GitHub securely
│   ├── repo_committer.py                # Commits generated files to GitHub
│   └── jenkins_configurator.py          # Applies config to Jenkins via API
│
├── webhook/                             # Receives pipeline failure events
│   ├── __init__.py
│   └── server.py                        # FastAPI webhook server
│
├── web_ui/                              # Optional simple web interface
│   ├── __init__.py
│   ├── app.py                           # Flask app
│   └── templates/
│       └── index.html
│
├── templates/                           # Base templates for generation
│   ├── jenkins/
│   │   ├── python_pipeline.groovy
│   │   ├── node_pipeline.groovy
│   │   ├── java_pipeline.groovy
│   │   └── docker_ecr_pipeline.groovy
│   └── github_actions/
│       ├── python_workflow.yml
│       ├── node_workflow.yml
│       ├── docker_ecr_workflow.yml
│       └── deploy_workflow.yml
│
├── config/
│   ├── __init__.py
│   └── settings.py                      # Reads all config from environment
│
├── tests/
│   ├── test_parser.py
│   ├── test_verifier.py
│   ├── test_analyzer.py
│   └── test_copilot.py
│
├── docs/
│   └── architecture.md
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## Component Breakdown

### providers/base.py
Abstract interface every LLM provider must implement. Ensures all providers are completely interchangeable.

```python
class BaseLLMProvider(ABC):
    async def complete(self, prompt, system, max_tokens, temperature) -> str
    def is_available(self) -> bool
```

### providers/factory.py
Reads task config from environment, instantiates the correct provider, handles fallback to Ollama if primary provider is unavailable.

### parser/pipeline_parser.py
Receives the full pipeline webhook payload. Returns a structured result identifying which stages passed, which stage failed first, the stage name, logs, and syntax definition. Passing stage logs are discarded immediately.

### parser/log_cleaner.py
Strips ANSI codes, timestamps, INFO lines. Keeps ERROR and WARN lines and 10 lines before first ERROR for context. Returns minimal clean log string typically under 300 tokens.

### verification/jenkins_crawler.py
The most original component. Does two things in sequence:

First — parses the Jenkinsfile or pipeline definition to extract every tool reference from tools{} block, sh steps, withCredentials blocks, and environment blocks.

Second — queries the Jenkins REST API to verify each reference against what is actually configured. Runs exact match and fuzzy match comparison and returns a structured verification report with facts only.

### verification/actions_crawler.py
Same concept for GitHub Actions. Parses workflow YAML to extract all secrets references, runner labels, action uses, and environment variables. Queries GitHub API to verify each one exists and is configured.

### analyzer/context_builder.py
Merges three inputs into a single optimized LLM payload: cleaned failed stage logs (~300 tokens), failed stage pipeline syntax (~200 tokens), tool verification report (~200 tokens). Total approximately 850 tokens regardless of full pipeline size.

### analyzer/cache.py
MD5 hash of the combined context used as cache key. Same failure signature returns cached response at zero cost.

### agent/fix_mapper.py
Maps failure diagnosis to specific fix action. Tool configuration mismatches, credential issues, and plugin problems are never auto-fixed — always produce an alert with precise diagnosis and require manual resolution.

### copilot/secrets_manager.py
Accepts secret values from user via web UI only. Sends directly to Jenkins credentials API or GitHub secrets API. Never logs or stores raw values beyond the single API call. Only injects variable references into generated pipeline files.

---

## LLM Provider System

### Provider abstraction
Every task specifies provider and model via environment variables. The factory reads config and returns the correct provider. All providers implement the same interface so task code never changes when providers change.

### Adding a new provider in future
1. Create providers/new_provider.py implementing BaseLLMProvider
2. Register in providers/factory.py
3. Add config keys to .env
4. Zero changes to any other file

### Fallback chain
```
Configured provider unavailable?
→ Try Ollama local
→ Ollama also unavailable?
→ web UI notification: manual review required
→ Never silently fail
```

---

## Model Routing Strategy

### Fully environment driven — zero hardcoding

```python
TASK_MODEL_MAP = {
    # No LLM — pure Python or API calls
    "parse_pipeline":           None,
    "clean_logs":               None,
    "crawl_tools":              None,
    "execute_fix":              None,
    "format_notification":      None,
    "handle_approval":          None,
    "commit_to_repo":           None,
    "manage_secrets":           None,

    # Haiku or Llama 8B — fast and sufficient for structured analysis
    "summarize_verification":   "claude-haiku-4-5-20251001",
    "analyze_logs":             "claude-haiku-4-5-20251001",
    "suggest_fix":              "claude-haiku-4-5-20251001",
    "explain_error":            "claude-haiku-4-5-20251001",
    "confidence_check":         "claude-haiku-4-5-20251001",

    # Sonnet or Qwen2.5-Coder 32B — quality critical generation
    "generate_jenkinsfile":     "claude-sonnet-4-6",
    "generate_actions_yaml":    "claude-sonnet-4-6",
    "plan_complex_fix":         "claude-sonnet-4-6",
    "review_generated_code":    "claude-sonnet-4-6",
}
```

### Environment switching examples

**Cloud API (cheapest real cost):**
```env
DEFAULT_PROVIDER=anthropic
LOG_ANALYSIS_MODEL=claude-haiku-4-5-20251001
PIPELINE_GENERATION_MODEL=claude-sonnet-4-6
```

**Full local — M4 MacBook 32GB:**
```env
DEFAULT_PROVIDER=ollama
LOG_ANALYSIS_MODEL=llama3.1:8b
PIPELINE_GENERATION_MODEL=qwen2.5-coder:32b
```

**Mixed — local for analysis, cloud for generation:**
```env
LOG_ANALYSIS_PROVIDER=ollama
LOG_ANALYSIS_MODEL=llama3.1:8b
PIPELINE_GENERATION_PROVIDER=anthropic
PIPELINE_GENERATION_MODEL=claude-sonnet-4-6
```

---

## Local Model Recommendations

Optimized for Apple M4 MacBook Air with 32GB unified memory and 2TB external SSD.

### For log analysis and failure diagnosis
**Llama 3.1 8B** — runs fast on M4 via Metal GPU acceleration, uses ~5-6GB RAM, accurate on structured log analysis with clean focused context. Primary recommendation for all reactive analysis tasks.

### For pipeline and YAML generation
**Qwen2.5-Coder 32B** — code-specialized model, outperforms Llama 70B specifically for generating Groovy, YAML, and infrastructure files. Fits in 32GB unified memory. Top recommendation for all copilot generation tasks.

**Llama 3.1 70B** — general purpose alternative, also fits in 32GB, good quality for generation.

### For verification report summarization
**Mistral 7B** — fast, accurate for short structured summarization, low RAM usage.

### Setup commands

```bash
# Store models on external SSD
export OLLAMA_MODELS=/Volumes/YourSSD/ollama-models
echo 'export OLLAMA_MODELS=/Volumes/YourSSD/ollama-models' >> ~/.zshrc

# Pull models
ollama pull llama3.1:8b        # ~4.7GB  — log analysis
ollama pull qwen2.5-coder:32b  # ~20GB   — pipeline generation
ollama pull mistral:7b         # ~4.1GB  — lightweight tasks
```

Total disk: ~29GB across all models.

---

## Cost Analysis

### Token usage per pipeline failure event

| Component | Tokens |
|---|---|
| Cleaned failed stage logs | ~300 |
| Failed stage pipeline syntax | ~200 |
| Tool verification report | ~200 |
| Prompt instructions | ~150 |
| Total input | ~850 |
| LLM output | ~400 |

Compare to feeding full pipeline: 10,000+ tokens. 90% reduction.

### Cost per call

| Model | Cost per analysis call |
|---|---|
| Claude Haiku 3.5 | ~$0.0000023 |
| Claude Sonnet 4.5 | ~$0.0000085 |
| Ollama local | $0.00 |

### Monthly production cost

| Activity | Volume | Model | Cost |
|---|---|---|---|
| Pipeline failures | 200/month | Haiku | $0.001 |
| Copilot generations | 100/month | Sonnet | $0.007 |
| Total | | | ~$0.01/month |

Development and testing phase: ~$0.015 total. Covered by Anthropic $5 free starter credits. Caching reduces costs a further 60-70% on projects with recurring errors.

---

## Fix Capabilities

### Pipeline Fixes

| Fix | Trigger |
|---|---|
| Retry pipeline | Transient failure or network timeout |
| Clear Docker build cache and retry | Layer cache corruption |
| Pull fresh base image and retry | Stale image issues |
| Clear npm / pip / maven cache and retry | Dependency cache corruption |
| Increase timeout and retry | Pipeline timeout errors |

### What Is Never Auto-Fixed

These always produce a diagnostic alert with no execute button. Manual resolution required.

- Tool name mismatches between Jenkinsfile and Jenkins Global Tool Configuration
- Missing or inactive plugins
- Missing or misconfigured credentials
- Missing secrets in GitHub Actions
- Runner label mismatches
- IAM permission issues
- Any fix requiring secret values

The agent provides exact diagnosis — for example: "Jenkinsfile references 'Maven-3.8' but Jenkins has 'Maven3' configured. Rename the tool in Jenkins or update the Jenkinsfile tools{} block" — and the human resolves the root cause.

---

## Copilot Capabilities

### Web UI Commands

```
generate jenkins python-docker-ecr
generate jenkins node-test-deploy
generate jenkins java-maven-ecr
generate actions python-test-ecr
generate actions node-staging-prod
add secret AWS_CREDENTIALS to pipeline
explain [paste Jenkinsfile or workflow YAML]
review [paste pipeline]
```

### What Gets Generated

**Jenkins Pipelines (Groovy):**
- Multi-stage pipelines with parallel execution
- Docker build and ECR push stages
- Deployment stages
- Environment-specific variable injection
- Shared library references
- Error handling and failure notifications

**GitHub Actions Workflows (YAML):**
- Full workflow with triggers
- Matrix build strategies
- Environment secrets injection
- Staging and production separation
- Reusable workflow references
- Docker and ECR deploy chains

### Generation Process

1. User sends natural language request via web UI
2. Agent loads relevant base template from templates/
3. Template plus user request sent to Sonnet or Qwen2.5-Coder
4. LLM fills template intelligently based on request
5. Generated file previewed in web UI
6. User reviews and clicks Approve / Modify / Cancel
7. On approval: committed to GitHub or applied to Jenkins via API
8. Confirmation shown in web UI with file path and commit link

---

## Web UI Interface

### Failure notification — tool mismatch example

```
🚨 Pipeline Failure Detected
────────────────────────────
Job:    build-and-deploy
Branch: main
Stage:  Build (Stage 3 of 6)

❌ What Failed:
Maven build failed — tool not found

🛠️ Tool Verification:
  Maven 'Maven-3.8':  NOT FOUND in Jenkins ❌
  Available:          'Maven3', 'maven-3.6'
  Best match:         'Maven3'

🔍 Root Cause:
Name mismatch. Jenkinsfile references 'Maven-3.8'
but Jenkins Global Tool Config has 'Maven3'.

💡 Fix:
Update Jenkinsfile:  maven 'Maven3'
OR rename tool in Jenkins to 'Maven-3.8'

🎯 Confidence: High

[📋 I'll Fix This Manually]
```

### Failure notification — auto-fixable example

```
🚨 Pipeline Failure Detected
────────────────────────────
Stage: Docker Build (Stage 4 of 6)

🛠️ Tool Verification:
  Docker installed:   ✅
  Daemon running:     ✅
  Registry creds:     ✅
  User in docker grp: ❌

🔍 Root Cause:
Jenkins user not in docker group.
Permission denied when calling Docker daemon.

💡 Fix:
Add Jenkins user to docker group and restart.

🎯 Confidence: High

[✅ Apply Fix]  [🔁 Retry]  [❌ Dismiss]
```

---

## Security Design

### Secrets handling
- Accepted only via web UI — never exposed in logs or shared channels
- Sent directly to Jenkins credentials API or GitHub secrets API
- Never stored in memory beyond the single API call
- Never logged to console, files, or audit log
- Only variable references appear in generated files: ${AWS_CREDENTIALS}
- Audit log records: secret name, who added it, timestamp — never the value

### Fix execution boundaries
- Every fix logged to audit log before execution begins
- Audit log is append-only — no deletions or modifications
- Tool config issues, credential issues, plugin issues never auto-fixed
- Confidence threshold enforced — low confidence shows no execute button

---

## Running Jenkins in Docker — Docker Socket Access

When Jenkins runs inside a Docker container and your Jenkinsfiles contain `docker build` or `docker push` commands, Jenkins needs access to the Docker daemon socket (`/var/run/docker.sock`).

### How it works

```
Your machine (macOS / Linux / Windows)
└── Docker daemon  ←── owns /var/run/docker.sock
    └── Jenkins container
        └── /var/run/docker.sock  (bind-mounted from host)
            └── Jenkinsfile: docker build ...  ──► talks to host daemon
```

The socket is mounted into the Jenkins container. Jenkins must have read/write permission on it.

### start.sh handles this automatically

`./start.sh` detects a running Jenkins container and fixes socket permissions on every startup:

| Platform | Method |
|---|---|
| **macOS** (Docker Desktop) | `chmod 666` on the mounted socket via `docker exec` |
| **Windows** (Docker Desktop) | Same as macOS |
| **Linux** | Adds `jenkins` user to `docker` group inside container |

You do not need to run anything manually — just run `./start.sh` as normal.

### Security note

`chmod 666` on the Docker socket grants **any process on the system** access to the Docker daemon, which is equivalent to root access. This is acceptable for a local development machine. Do not use this approach in a shared or production environment — use Docker-in-Docker (dind) or a rootless Docker setup instead.

### If you manage Jenkins outside start.sh

Run once after every Docker Desktop restart:

```bash
# macOS / Windows (Docker Desktop)
docker exec -u root jenkins chmod 666 /var/run/docker.sock

# Linux
docker exec -u root jenkins usermod -aG docker jenkins
```

---

## Configuration Reference

### .env.example

```env
# ── LLM ROUTING ──────────────────────────────────────────

DEFAULT_PROVIDER=anthropic
# Options: anthropic, ollama

LOG_ANALYSIS_PROVIDER=anthropic
LOG_ANALYSIS_MODEL=claude-haiku-4-5-20251001

VERIFICATION_SUMMARY_PROVIDER=anthropic
VERIFICATION_SUMMARY_MODEL=claude-haiku-4-5-20251001

FIX_SUGGESTION_PROVIDER=anthropic
FIX_SUGGESTION_MODEL=claude-haiku-4-5-20251001

PIPELINE_GENERATION_PROVIDER=anthropic
PIPELINE_GENERATION_MODEL=claude-sonnet-4-6

# ── CONFIDENCE THRESHOLD ─────────────────────────────────

MIN_CONFIDENCE_FOR_EXECUTE=high
# Options: high, medium, low

# ── PROVIDER CREDENTIALS ─────────────────────────────────

ANTHROPIC_API_KEY=sk-ant-...

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b
OLLAMA_MODELS=/Volumes/YourSSD/ollama-models

# ── JENKINS ──────────────────────────────────────────────

JENKINS_URL=http://localhost:8080
JENKINS_USER=admin
JENKINS_TOKEN=your_jenkins_api_token

# ── GITHUB ───────────────────────────────────────────────

GITHUB_TOKEN=ghp_...
GITHUB_REPO_OWNER=adil-khan-723
GITHUB_DEFAULT_BRANCH=main

# ── AWS ──────────────────────────────────────────────────

AWS_DEFAULT_REGION=ap-south-1
ECR_REGISTRY=your_account_id.dkr.ecr.ap-south-1.amazonaws.com

# ── CACHING ──────────────────────────────────────────────

CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600

# ── WEBHOOK SERVER ────────────────────────────────────────

WEBHOOK_PORT=8000
WEBHOOK_SECRET=your_webhook_secret

# ── LOGGING ──────────────────────────────────────────────

LOG_LEVEL=INFO
AUDIT_LOG_PATH=./logs/audit.log
```

---

## Build Phases & Timeline

### Phase 1 — Foundation (Week 1)
- FastAPI webhook server receives pipeline failure events
- Pipeline parser identifies failed stage
- Log extractor pulls only failed stage logs
- Log cleaner strips noise
- Basic Ollama integration for free local testing
- Web UI notifier sends formatted message
- No fix execution yet — observation only

Milestone: Pipeline fails → clean analysis posted to web UI

### Phase 2 — Tool Verification Crawler (Week 2)
- Jenkins crawler — parse Jenkinsfile tool references from tools{} block and sh steps
- Jenkins API queries for configured tools, plugins, credentials
- Exact match and fuzzy match comparison logic
- GitHub Actions crawler — parse workflow YAML for secrets, runners, actions
- GitHub API queries for secrets and runner availability
- Context builder merges logs + verification report
- Confidence threshold implementation

Milestone: Tool mismatches detected and reported precisely before LLM call

### Phase 3 — Approval Flow and Fix Execution (Week 3)
- Web UI approval handler
- Button interactions — Approve, Retry, Dismiss
- Audit log implementation
- Fix executor for pipeline-level fixes
- Pipeline rerun after fix applied
- Response caching layer
- Fallback chain implementation

Milestone: User approves fixes via web UI, agent executes and reports result

### Phase 4 — Copilot Mode (Week 4)
- Pipeline generator for Jenkins Groovy
- GitHub Actions YAML generator
- Base templates for common patterns
- Web UI command handler
- Repo committer via GitHub API
- Jenkins configurator via API

Milestone: Generate complete pipelines from natural language in web UI

### Phase 5 — Secrets Management and Polish (Week 5)
- Secrets manager for Jenkins and GitHub
- Multi-provider LLM support fully wired
- Provider factory with fallback chain tested
- Docker Compose full stack setup
- Optional simple web UI

Milestone: Full system running end to end locally

### Phase 6 — Documentation and Publication (Week 6)
- Comprehensive README with architecture diagram
- Test coverage for core components
- GitHub repo cleanup
- Dev.to article: Building a Human-in-the-Loop AI Agent for CI/CD Failure Recovery
- LinkedIn post with architecture walkthrough

Milestone: Published, documented, live on GitHub

---

## Resume Value

### Resume line

Built an AI-powered CI/CD Copilot using local and cloud LLMs (Ollama/Llama 3.1, Qwen2.5-Coder 32B, Claude Haiku/Sonnet) with a deterministic tool-verification crawler that cross-checks Jenkins Global Tool Configuration and GitHub Actions secrets against pipeline definitions before LLM analysis — achieving 90% token reduction through selective context feeding, human-in-the-loop approval via web UI, automated fix execution, and a Copilot mode for generating Jenkinsfiles and GitHub Actions workflows from natural language.

### Key interview talking points

**On selective context feeding:**
Instead of feeding the entire pipeline log to the LLM, I parse the result first and only send the failed stage — about 850 tokens instead of 10,000 plus. That is a 90% token reduction with better accuracy because the LLM is not distracted by passing stage noise.

**On the tool verification crawler:**
One of the most common CI/CD failures is a tool name mismatch — the Jenkinsfile references a tool name that does not exactly match what is configured in Jenkins Global Tool Configuration. My crawler detects this deterministically before calling the LLM by parsing the Jenkinsfile, querying the Jenkins API, and running exact plus fuzzy match comparison. The LLM receives verified facts instead of guessing from confusing error messages. This eliminates an entire category of hallucination.

**On human-in-the-loop:**
The agent never executes anything automatically. Every fix requires explicit approval in the web UI. Tool configuration issues, credential problems, and plugin issues never get an auto-fix button at all — always manual resolution. This is how production AI systems are designed responsibly.

**On the provider abstraction:**
No model is hardcoded anywhere. The entire system switches from Claude to locally running Llama or Qwen with one environment variable change. The task code never knows which provider it is talking to. On my M4 MacBook with 32GB I can run Qwen2.5-Coder 32B locally for free for all generation tasks.

**On cost:**
The entire system costs about one cent per month in production. The 90% token optimization, caching, and smart model routing make it essentially free at any reasonable scale.

---

## Developer

**Adil Khan**
DevOps Engineer | 
HashiCorp Certified Terraform Associate (004)

- GitHub: https://github.com/adil-khan-723
- LinkedIn: https://www.linkedin.com/in/adilk3682
- Dev.to: https://dev.to/adil-khan-723
- Email: adilk81054@gmail.com

---

*This README is the complete living specification for the DevOps AI Agent project. Every architectural decision, optimization, clarification, and component discussed during planning is documented here. Scope is strictly CI/CD — Jenkins and GitHub Actions. Kubernetes cluster monitoring and management is out of scope and belongs to a separate project. Use this as the source of truth when switching between development sessions or chat contexts.*
