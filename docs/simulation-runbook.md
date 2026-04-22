# DevOps AI Agent — Simulation Runbook

Full walkthrough of every scenario the system handles, from startup to edge cases.
Run these in order: environment → unit checks → reactive flow → copilot → edge cases → failure injection.

---

## 1. Environment Setup

### 1a. Prerequisites

```bash
# Confirm Python 3.11+
python3 --version

# Create and activate venv (already exists if scaffold is done)
python3 -m venv .venv
source .venv/bin/activate  # Mac/Linux

# Install all dependencies
pip install -r requirements.txt

# Verify install
pytest --version   # should print pytest 9.x
```

### 1b. Configure .env

```bash
cp .env.example .env
```

Minimum viable `.env` for local simulation (no Ollama, no live Jenkins):

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_ANALYSIS_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_GENERATION_MODEL=claude-sonnet-4-6
CONFIDENCE_THRESHOLD=0.75
JENKINS_URL=http://localhost:8080
JENKINS_USER=admin
JENKINS_TOKEN=
GITHUB_TOKEN=
AUDIT_LOG_PATH=audit.log
LOG_LEVEL=DEBUG
WEBHOOK_SECRET=
```

To use Ollama locally instead:
```
LLM_PROVIDER=ollama
ANALYSIS_MODEL=llama3.1:8b
GENERATION_MODEL=qwen2.5-coder:14b
OLLAMA_BASE_URL=http://localhost:11434
```

Switch at any time — zero code changes.

### 1c. Run the Full Test Suite (Baseline Check)

```bash
.venv/bin/pytest tests/ -v
```

Expected: **163 passed**. If any fail, stop and fix before simulating.

---

## 2. Unit-Level Simulation (No Live Services)

These check each component in isolation using the Python REPL.
Run `python3` (or `.venv/bin/python`) from the project root.

### 2a. Log Pipeline: Parse → Extract → Clean

```python
from parser.pipeline_parser import parse_failure
from parser.log_extractor import extract_failed_logs
from parser.log_cleaner import clean_log

# Simulate a Jenkins webhook payload with embedded log
jenkins_payload = {
    "job_name": "build-api",
    "build_number": 42,
    "branch": "main",
    "log": """
[Pipeline] stage (Checkout)
Cloning repository...
[Pipeline] stage (Docker Build)
[INFO] Building image...
ERROR: Cannot connect to the Docker daemon
FAILURE: Build failed in stage Docker Build
[Pipeline] stage (Test)
Skipped.
"""
}

ctx = parse_failure(jenkins_payload, source="jenkins")
print(ctx.job_name)       # build-api
print(ctx.failed_stage)   # Docker Build
print(ctx.platform)       # jenkins

extracted = extract_failed_logs(ctx)
print(extracted)           # only the Docker Build block, <= 2000 chars

cleaned = clean_log(extracted)
print(cleaned)             # ANSI gone, timestamps gone, [INFO] gone
```

**Expected:** `failed_stage = "Docker Build"`. Extracted block is ~40 chars. Cleaned output is readable prose.

---

### 2b. GitHub Actions Payload

```python
from parser.pipeline_parser import parse_failure
from parser.log_extractor import extract_failed_logs

github_payload = {
    "workflow_run": {
        "name": "CI",
        "run_number": 99,
        "head_branch": "feature/login",
        "repository": {"full_name": "adil-khan-723/app"},
    },
    "failed_job": "build / Push to ECR",
    "log": """
##[group]Run docker build
Building image...
##[endgroup]
##[group]Run Push to ECR
Error: denied: User not authorized to push
##[endgroup]
"""
}

ctx = parse_failure(github_payload, source="github")
print(ctx.failed_stage)   # build / Push to ECR
print(ctx.platform)       # github

extracted = extract_failed_logs(ctx)
print(extracted)           # only the Push to ECR block
```

---

### 2c. Context Builder (Token Budget Check)

```python
from analyzer.context_builder import build_context
from parser.models import FailureContext
from verification.models import VerificationReport, ToolMismatch

ctx = FailureContext(
    job_name="build-api",
    build_number=42,
    failed_stage="Docker Build",
    platform="jenkins",
    raw_log="",
    branch="main",
)

report = VerificationReport(platform="jenkins")
report.mismatches.append(ToolMismatch(
    tool_type="maven",
    referenced_name="Maven3",
    configured_name="Maven-3",
    match_score=0.91,
))

context_str = build_context(
    log="Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
    report=report,
    context=ctx,
)

print(context_str)

# Check token budget
words = context_str.split()
print(f"Approx tokens: {len(words)}")   # Should be < 900
```

**Expected:** Context string contains metadata, mismatch finding, and log. Token estimate ~400-600.

---

### 2d. Response Parser (All Branches)

```python
from analyzer.response_parser import parse_analysis_response

# Happy path — clean JSON
r = parse_analysis_response('{"root_cause": "Docker daemon not running", "fix_suggestion": "Retry after starting daemon", "confidence": 0.88, "fix_type": "retry"}')
print(r)   # fix_type=retry, confidence=0.88

# JSON wrapped in markdown fence (common LLM output)
r = parse_analysis_response('Sure! Here is the analysis:\n```json\n{"root_cause": "Cache stale", "fix_suggestion": "Clear Docker cache", "confidence": 0.82, "fix_type": "clear_cache"}\n```')
print(r)   # correctly extracted

# Low confidence — forced to diagnostic_only
r = parse_analysis_response('{"root_cause": "Unknown error", "fix_suggestion": "Check logs", "confidence": 0.45, "fix_type": "retry"}')
print(r["fix_type"])   # diagnostic_only (confidence < 0.6 overrides fix_type)

# Unknown fix_type — defaults to diagnostic_only
r = parse_analysis_response('{"root_cause": "Something bad", "fix_suggestion": "Fix it", "confidence": 0.9, "fix_type": "delete_everything"}')
print(r["fix_type"])   # diagnostic_only

# Totally broken JSON
r = parse_analysis_response("I cannot determine the root cause at this time.")
print(r["fix_type"])   # diagnostic_only, confidence=0.0

# Empty string
r = parse_analysis_response("")
print(r["confidence"])   # 0.0
```

---

### 2e. Fix Executor (Safety Gate Check)

```python
from agent.fix_executor import execute_fix

# diagnostic_only is NEVER executed, no matter what
result = execute_fix("diagnostic_only", job_name="build-api")
print(result.success)   # False
print(result.detail)    # "This issue requires manual intervention..."

# Unknown fix_type → treated as diagnostic
result = execute_fix("delete_everything", job_name="build-api")
print(result.success)   # False
print(result.detail)    # "Unknown fix type..."
```

**Key invariant:** `diagnostic_only` never reaches Jenkins. No exceptions.

---

### 2f. Audit Log

```python
import os, json, tempfile
from unittest.mock import patch
from agent.audit_log import log_fix, read_recent

tmp = tempfile.mktemp(suffix=".log")
with patch("agent.audit_log.get_settings") as m:
    m.return_value.audit_log_path = tmp

    log_fix("retry", "U123", "build-api", "42", "success", 0.88)
    log_fix("clear_cache", "U456", "build-api", "43", "failed", 0.77)

with open(tmp) as f:
    for line in f:
        entry = json.loads(line)
        print(entry)
        # Verify: no "sk-", no "xoxb-", no token values
        for v in entry.values():
            assert not str(v).startswith("sk-")

print("Two entries, append-only, no secrets ✓")
os.unlink(tmp)
```

---

### 2g. Response Cache (MD5 Keyed)

```python
from analyzer.cache import get, set as cache_set, clear

clear()

# Miss
result = get("same failure log")
print(result)   # None

# Set
cache_set("same failure log", {"root_cause": "Docker down", "fix_type": "retry", "confidence": 0.88, "fix_suggestion": "Retry"})

# Hit
result = get("same failure log")
print(result["fix_type"])   # retry

# Different context → different key
result2 = get("different failure log")
print(result2)   # None
```

---

### 2h. Provider Factory (Fallback Chain)

```python
from unittest.mock import patch, MagicMock

# Simulate: primary (ollama) down, fallback (groq) up
with patch("providers.factory.get_settings") as mock_s:
    mock_s.return_value.llm_provider = "ollama"
    mock_s.return_value.llm_fallback_provider = "groq"
    mock_s.return_value.analysis_model = "llama3.1:8b"
    mock_s.return_value.generation_model = "qwen2.5-coder:14b"
    mock_s.return_value.ollama_base_url = "http://localhost:11434"
    mock_s.return_value.ollama_timeout = 30

    with patch("providers.ollama_provider.get_settings", mock_s), \
         patch("providers.groq_provider.get_settings") as groq_s:
        groq_s.return_value.groq_api_key = "gsk_test"
        groq_s.return_value.groq_model = "llama-3.3-70b-versatile"

        with patch("providers.ollama_provider.OllamaProvider.is_available", return_value=False), \
             patch("providers.groq_provider.GroqProvider.is_available", return_value=True):
            from providers.factory import get_provider
            provider = get_provider("analysis")
            print(provider.name)   # groq/llama-3.3-70b-versatile  ← fallback activated
```

---

### 2i. Template Selector (Copilot Mode)

```python
from copilot.template_selector import select_template, list_templates

# Exact match
tmpl = select_template("jenkins", "python docker ecr build push")
print(tmpl)   # jenkins/python-docker-ecr.groovy

# Node.js (tests tokenizer on "node.js" → {node, js})
tmpl = select_template("jenkins", "node.js docker build deploy")
print(tmpl)   # jenkins/node-docker.groovy

# Falls back to generic
tmpl = select_template("jenkins", "something completely unknown")
print(tmpl)   # jenkins/generic.groovy

# GitHub Actions
tmpl = select_template("github", "python run test lint")
print(tmpl)   # github/python-ci.yml

# List all available templates
print(list_templates("jenkins"))   # ['python-docker-ecr', 'node-docker', 'generic']
print(list_templates("github"))    # ['python-ci', 'docker-ecr', 'generic']
```

---

## 3. Webhook Server Simulation

### 3a. Start the Server

```bash
.venv/bin/uvicorn webhook.server:app --reload --port 8000
```

### 3b. Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 3c. Jenkins Failure Webhook

```bash
curl -X POST http://localhost:8000/webhook/pipeline-failure \
  -H "Content-Type: application/json" \
  -H "X-Jenkins-Event: run.finalized" \
  -d '{
    "job_name": "build-api",
    "build_number": 42,
    "result": "FAILURE",
    "branch": "main",
    "failed_stage": "Docker Build",
    "log": "[Pipeline] stage (Checkout)\nClone OK\n[Pipeline] stage (Docker Build)\nERROR: Cannot connect to the Docker daemon\nFAILURE"
  }'
# {"status":"received","source":"jenkins"}
```

### 3d. GitHub Actions Failure Webhook

```bash
curl -X POST http://localhost:8000/webhook/pipeline-failure \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -d '{
    "workflow_run": {
      "name": "CI",
      "run_number": 99,
      "head_branch": "feature/login",
      "repository": {"full_name": "adil-khan-723/app"},
      "conclusion": "failure"
    },
    "failed_job": "build / Push to ECR",
    "log": "##[group]Run Push to ECR\nError: denied: User not authorized\n##[endgroup]"
  }'
# {"status":"received","source":"github"}
```

### 3e. Unknown Source (No Signature Headers)

```bash
curl -X POST http://localhost:8000/webhook/pipeline-failure \
  -H "Content-Type: application/json" \
  -d '{"job_name": "mystery-job", "build_number": 1}'
# {"status":"received","source":"unknown"} — accepted in dev (no strict validation)
```

---

## 4. Jenkins Verification Crawler Simulation

```python
import respx, httpx
from verification.jenkins_crawler import verify_jenkins_tools

jenkinsfile = """
pipeline {
  agent any
  tools {
    maven 'Maven3'
    jdk 'JDK11'
  }
  stages {
    stage('Build') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'ECR_CREDENTIALS', ...)]) {
          sh 'mvn clean package'
        }
      }
    }
  }
}
"""

with respx.mock:
    # Global tools API — Jenkins has "Maven-3" not "Maven3"
    respx.get("http://jenkins:8080/api/json").mock(
        return_value=httpx.Response(200, json={
            "tools": [
                {"type": "hudson.tasks.Maven$MavenInstallation", "name": "Maven-3"},
                {"type": "hudson.model.JDK", "name": "JDK11"},
            ]
        })
    )
    # Plugin manager — both plugins installed
    respx.get("http://jenkins:8080/pluginManager/api/json").mock(
        return_value=httpx.Response(200, json={
            "plugins": [
                {"shortName": "maven-plugin", "active": True},
                {"shortName": "jdk-tool", "active": True},
            ]
        })
    )
    # Credentials — ECR_CREDENTIALS missing
    respx.get("http://jenkins:8080/credentials/store/system/domain/_/api/json").mock(
        return_value=httpx.Response(200, json={"credentials": []})
    )

    report = verify_jenkins_tools(jenkinsfile, "http://jenkins:8080")

print(report.has_issues)      # True
print(report.summary_lines())
# Tool mismatch: maven 'Maven3' → closest configured: 'Maven-3' (91% match)
# Missing credential: ECR_CREDENTIALS
```

---

## 5. GitHub Actions Verification Crawler Simulation

```python
import respx, httpx
from verification.actions_crawler import verify_actions_config

workflow_yaml = """
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - name: Push to ECR
        run: docker push $ECR_REPO
        env:
          AWS_ACCESS_KEY: ${{ secrets.AWS_ACCESS_KEY }}
          ECR_TOKEN: ${{ secrets.ECR_TOKEN }}
"""

with respx.mock:
    # Only AWS_ACCESS_KEY exists — ECR_TOKEN missing
    respx.get("https://api.github.com/repos/adil-khan-723/app/actions/secrets").mock(
        return_value=httpx.Response(200, json={
            "secrets": [{"name": "AWS_ACCESS_KEY"}]
        })
    )

    report = verify_actions_config(
        workflow_yaml,
        github_repo="adil-khan-723/app",
        github_token="ghp_test",
    )

print(report.has_issues)      # True
print(report.summary_lines())
# Missing secret: ECR_TOKEN
# Unpinned action: actions/checkout@main — pin to a commit SHA for reproducibility
```

---

## 6. Full Reactive Pipeline Simulation (End-to-End, All Mocked)

This simulates the complete failure → analysis → web UI message flow without any live services.

```python
import json
from unittest.mock import patch, MagicMock
from parser.pipeline_parser import parse_failure
from parser.log_extractor import extract_failed_logs
from parser.log_cleaner import clean_log
from analyzer.context_builder import build_context
from web_ui.message_templates import failure_alert_blocks, analysis_complete_blocks

# --- Step 1: Receive Jenkins failure ---
payload = {
    "job_name": "build-api",
    "build_number": 42,
    "branch": "main",
    "failed_stage": "Docker Build",
    "log": "[Pipeline] stage (Docker Build)\nERROR: Cannot connect to the Docker daemon at unix:///var/run/docker.sock\nFAILURE: Build failed",
}
ctx = parse_failure(payload, source="jenkins")
print(f"[1] Parsed: {ctx.job_name} #{ctx.build_number}, stage={ctx.failed_stage}")

# --- Step 2: Extract + clean log ---
extracted = extract_failed_logs(ctx)
cleaned = clean_log(extracted)
print(f"[2] Cleaned log ({len(cleaned)} chars): {cleaned[:80]}...")

# --- Step 3: Run verification (mocked Jenkins API) ---
from verification.models import VerificationReport
report = VerificationReport(platform="jenkins")
# Pretend crawler found no issues
print(f"[3] Verification: has_issues={report.has_issues}")

# --- Step 4: Build LLM context ---
context_str = build_context(cleaned, report, ctx)
print(f"[4] Context built (~{len(context_str.split())} tokens)")

# --- Step 5: LLM analysis (mocked provider) ---
mock_raw = '{"root_cause": "Docker daemon not running on the build node", "fix_suggestion": "Retry pipeline — daemon auto-recovers", "confidence": 0.88, "fix_type": "retry"}'

from analyzer.response_parser import parse_analysis_response
analysis = parse_analysis_response(mock_raw)
print(f"[5] Analysis: {analysis['root_cause']} (confidence={analysis['confidence']}, fix={analysis['fix_type']})")

# --- Step 6: Build web UI notification blocks ---
blocks = failure_alert_blocks(ctx, cleaned, report=report, analysis=analysis)
updated_blocks = analysis_complete_blocks(blocks, analysis, confidence_threshold=0.75)

# Find the actions block
actions = [b for b in updated_blocks if b.get("type") == "actions"]
print(f"[6] Web UI buttons: {[e['text']['text'] for e in actions[0]['elements']]}")
# ['Apply Fix (Retry)', 'Dismiss']

# --- Step 7: User clicks Apply Fix → execute fix (mocked Jenkins) ---
from agent.fix_executor import execute_fix

with patch("agent.pipeline_fixes._get_jenkins_server") as mock_j:
    mock_server = MagicMock()
    mock_j.return_value = mock_server
    result = execute_fix("retry", "build-api", "42")

print(f"[7] Fix result: success={result.success}, detail={result.detail}")

# --- Step 8: Audit log entry ---
import tempfile, os
tmp = tempfile.mktemp(suffix=".log")
with patch("agent.audit_log.get_settings") as m:
    m.return_value.audit_log_path = tmp
    from agent.audit_log import log_fix
    log_fix("retry", "U_ADIL", "build-api", "42", "success", 0.88)

with open(tmp) as f:
    entry = json.loads(f.readline())
print(f"[8] Audit: {entry}")
os.unlink(tmp)

print("\n✓ Full reactive pipeline simulation complete.")
```

---

## 7. Copilot Mode Simulation

```python
from unittest.mock import patch, MagicMock
from copilot.template_selector import select_template
from copilot.pipeline_generator import generate_jenkinsfile
from copilot.actions_generator import generate_workflow

# --- Jenkins pipeline generation ---
template = select_template("jenkins", "python docker ecr build push")
print(f"Template selected: {template}")

MOCK_JENKINSFILE = """pipeline {
  agent any
  stages {
    stage('Build') { steps { sh 'docker build .' } }
    stage('Push') { steps { sh 'docker push ecr/app' } }
  }
}"""

with patch("copilot.pipeline_generator.get_provider") as mock_p:
    mock_provider = MagicMock()
    mock_provider.complete.return_value = MOCK_JENKINSFILE
    mock_p.return_value = mock_provider

    content, tmpl_name = generate_jenkinsfile("python app, docker build, push to ECR")
    print(f"Generated Jenkinsfile ({len(content)} chars) using template: {tmpl_name}")

# --- GitHub Actions workflow generation ---
MOCK_WORKFLOW = """name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker
        run: docker build .
"""

with patch("copilot.actions_generator.get_provider") as mock_p:
    mock_provider = MagicMock()
    mock_provider.complete.return_value = MOCK_WORKFLOW
    mock_p.return_value = mock_provider

    content = generate_workflow("node.js app, run tests, build docker, deploy to EC2")
    print(f"Generated workflow ({len(content)} chars)")

print("\n✓ Copilot mode simulation complete.")
```

---

## 8. Failure Injection — How the System Behaves When Things Go Wrong

### 8a. Ollama Down → Fallback to Groq

```python
import respx, httpx
from unittest.mock import patch, MagicMock

with patch("providers.factory.get_settings") as mock_s:
    mock_s.return_value.llm_provider = "ollama"
    mock_s.return_value.llm_fallback_provider = "groq"
    mock_s.return_value.analysis_model = "llama3.1:8b"
    mock_s.return_value.generation_model = "qwen2.5-coder:14b"
    mock_s.return_value.ollama_base_url = "http://localhost:11434"
    mock_s.return_value.ollama_timeout = 30

    with patch("providers.groq_provider.get_settings") as groq_s:
        groq_s.return_value.groq_api_key = "gsk_real_key"
        groq_s.return_value.groq_model = "llama-3.3-70b-versatile"

        # Ollama is not reachable
        with patch("providers.ollama_provider.OllamaProvider.is_available", return_value=False), \
             patch("providers.groq_provider.GroqProvider.is_available", return_value=True):

            from providers.factory import get_provider
            provider = get_provider("analysis")
            print(f"Provider selected: {provider.name}")
            # groq/llama-3.3-70b-versatile ← fallback activated automatically
```

### 8b. All Providers Down → ProviderUnavailableError

```python
from providers.factory import get_provider, ProviderUnavailableError
from unittest.mock import patch

with patch("providers.factory.get_settings") as mock_s:
    mock_s.return_value.llm_provider = "ollama"
    mock_s.return_value.llm_fallback_provider = "groq"
    mock_s.return_value.analysis_model = "llama3.1:8b"
    mock_s.return_value.generation_model = "qwen2.5-coder:14b"
    mock_s.return_value.ollama_base_url = "http://localhost:11434"
    mock_s.return_value.ollama_timeout = 30

    with patch("providers.groq_provider.get_settings") as groq_s:
        groq_s.return_value.groq_api_key = "gsk_key"
        groq_s.return_value.groq_model = "llama-3.3-70b-versatile"

        with patch("providers.ollama_provider.OllamaProvider.is_available", return_value=False), \
             patch("providers.groq_provider.GroqProvider.is_available", return_value=False):
            try:
                provider = get_provider("analysis")
            except ProviderUnavailableError as e:
                print(f"Caught: {e}")
                # "All LLM providers unavailable (tried: ['ollama', 'groq'])"
```

### 8c. LLM Returns Garbage → Safe Fallback

```python
from analyzer.response_parser import parse_analysis_response

bad_outputs = [
    "",                                      # empty
    "I cannot help with that.",              # prose, no JSON
    "{ broken json",                         # malformed
    '{"confidence": 0.3, "fix_type": "retry"}',  # low confidence
    '{"root_cause": "", "fix_type": "retry", "confidence": 0.9}',  # empty root_cause
]

for bad in bad_outputs:
    result = parse_analysis_response(bad)
    assert result["fix_type"] == "diagnostic_only", f"Expected diagnostic_only, got: {result}"
    assert result["confidence"] == 0.0 or result["confidence"] < 0.6
    print(f"Input: {bad[:40]!r} → fix_type={result['fix_type']} confidence={result['confidence']}")

print("\n✓ All garbage inputs safely fallback to diagnostic_only")
```

### 8d. GitHub API Returns 403 (No Secret Read Permission)

```python
import respx, httpx
from verification.actions_crawler import verify_actions_config

workflow_yaml = """
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.DEPLOY_TOKEN }}
"""

with respx.mock:
    # API returns 403 — no permission to list secrets
    respx.get("https://api.github.com/repos/adil-khan-723/app/actions/secrets").mock(
        return_value=httpx.Response(403, json={"message": "Resource not accessible"})
    )

    report = verify_actions_config(
        workflow_yaml,
        github_repo="adil-khan-723/app",
        github_token="ghp_limited_token",
    )

# Should NOT flag DEPLOY_TOKEN as missing — 403 means "can't verify", not "missing"
print(f"has_issues: {report.has_issues}")   # False — silently skipped
print(f"errors: {report.errors}")           # [] — not an error, just skipped
print("✓ 403 handled gracefully — no false positives")
```

### 8e. Jenkins Unreachable → Verification Error, Pipeline Continues

```python
import respx, httpx
from verification.jenkins_crawler import verify_jenkins_tools

jenkinsfile = "pipeline { tools { maven 'Maven3' } stages { stage('Build') { steps { sh 'mvn package' } } } }"

with respx.mock:
    respx.get("http://jenkins:8080/api/json").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    report = verify_jenkins_tools(jenkinsfile, "http://jenkins:8080")

print(f"errors: {report.errors}")     # ["Cannot reach Jenkins at http://jenkins:8080"]
print(f"has_issues: {report.has_issues}")   # True (errors count as issues)
print("✓ Jenkins unreachable → error flagged, pipeline analysis continues")
```

### 8f. Webhook With No Matching Stage in Log

```python
from parser.pipeline_parser import parse_failure
from parser.log_extractor import extract_failed_logs

# Log with no stage markers
payload = {
    "job_name": "mystery-job",
    "build_number": 1,
    "log": "Some raw output\nERROR: something bad\nProcess exited 1",
}

ctx = parse_failure(payload, source="jenkins")
print(f"failed_stage: {ctx.failed_stage}")   # "unknown-stage" (graceful fallback)

extracted = extract_failed_logs(ctx)
print(f"extracted ({len(extracted)} chars)")   # returns tail of log — always returns something
```

### 8g. Tool Name Mismatch — Fuzzy Match

```python
import respx, httpx
from verification.jenkins_crawler import verify_jenkins_tools

jenkinsfile = "pipeline { tools { maven 'Maven3' } stages { stage('Build') { steps { sh 'mvn' } } } }"

with respx.mock:
    # Jenkins has "Maven-3" — Levenshtein similarity = 0.91 → caught as mismatch
    respx.get("http://jenkins:8080/api/json").mock(
        return_value=httpx.Response(200, json={
            "tools": [{"type": "hudson.tasks.Maven$MavenInstallation", "name": "Maven-3"}]
        })
    )
    respx.get("http://jenkins:8080/pluginManager/api/json").mock(
        return_value=httpx.Response(200, json={"plugins": []})
    )
    respx.get("http://jenkins:8080/credentials/store/system/domain/_/api/json").mock(
        return_value=httpx.Response(200, json={"credentials": []})
    )

    report = verify_jenkins_tools(jenkinsfile, "http://jenkins:8080")

mismatch = report.mismatches[0]
print(f"Mismatch: '{mismatch.referenced_name}' → closest: '{mismatch.configured_name}' ({mismatch.match_score:.0%} match)")
# Mismatch: 'Maven3' → closest: 'Maven-3' (91% match)
print("✓ Fuzzy match caught near-miss tool name — LLM given a fact, not a log to guess from")
```

### 8h. Cache Hit on Repeated Failure

```python
from analyzer.cache import get, set as cache_set, clear
import time

clear()

context = "build-api #42 Docker Build: ERROR: Cannot connect to Docker daemon"
result = {"root_cause": "Docker down", "fix_type": "retry", "confidence": 0.88, "fix_suggestion": "Retry"}

# First call — miss
assert get(context) is None

# Cache the result
cache_set(context, result)

# Second call (same failure) — hit, no LLM call needed
hit = get(context)
assert hit == result
print("✓ Same failure context → cache hit → zero LLM cost on repeat failures")

# Simulate TTL expiry
from analyzer.cache import _store
import hashlib
key = hashlib.md5(context.encode()).hexdigest()
_store[key] = (time.time() - 4000, result)   # force expire (4000s > 3600s TTL)
assert get(context) is None
print("✓ TTL expired → cache miss → fresh LLM call")
```

---

## 9. Run Full Test Suite + Coverage Report

```bash
.venv/bin/pytest tests/ -v --tb=short 2>&1 | tee simulation-test-output.txt

.venv/bin/pytest tests/ --cov=. --cov-report=term-missing --ignore=.venv -q
```

Expected:
- **163 passed**
- **84% overall coverage**
- 0% on `web_ui/approval_handler.py`, `web_ui/copilot_handler.py`, `webhook/server.py` — these require live web UI sessions or HTTP connections, not testable without real services

---

## 10. What Each Coverage Gap Means

| File | Coverage | Why 0% is OK |
|---|---|---|
| `web_ui/approval_handler.py` | 0% | Button click handlers — require live web UI session |
| `web_ui/copilot_handler.py` | 0% | Command handlers — require live web UI session |
| `webhook/server.py` | 0% | FastAPI server — tested via curl in section 3 |
| `webhook/validators.py` | 0% | HMAC validation — tested via live curl |
| `copilot/secrets_manager.py` | 42% | Secrets input flow — requires live web UI session |
| `web_ui/notifier.py` | 58% | Live notification dispatch calls |
| `agent/pipeline_fixes.py` | 64% | Live Jenkins API calls — tested via mock in executor |

All critical logic paths (parsing, verification, analysis, audit, caching, fallback) are covered.

---

## 11. Live Run Checklist (When You Have Real Services)

When Jenkins, web UI, and an LLM are all live:

```
[ ] uvicorn webhook.server:app --reload --port 8000
[ ] python -m web_ui.app  (in a separate terminal)
[ ] Send Jenkins failure webhook (section 3c)
[ ] Watch web UI notification panel — alert should appear within 5s
[ ] Watch DEBUG logs — see: parse → extract → clean → verify → context → LLM → web UI
[ ] Click "Apply Fix" — watch audit.log for new entry
[ ] Send same webhook again — watch cache hit in DEBUG logs (no LLM call made)
[ ] Kill Ollama (if local) — watch fallback provider activate in logs
[ ] Kill all providers — watch ProviderUnavailableError → "Manual Review" button only
[ ] Submit "generate jenkins python docker ecr" in web UI
[ ] Click "Approve & Commit" — verify file appears in GitHub repo
```

---

*Generated: 2026-04-09*
