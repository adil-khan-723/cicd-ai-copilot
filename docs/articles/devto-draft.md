# Building a human-in-the-loop AI agent for CI/CD failure recovery

---

*tags: devops, ai, cicd, python*

---

My pipelines break every week. Usually Docker cache issues, sometimes a pip dependency conflict, occasionally a missing credential that someone rotated and forgot to update. Each one takes 20-40 minutes to diagnose. Most of that time is spent opening logs, figuring out which stage failed, cross-checking job config, then deciding what to actually fix.

I built a tool that does most of that for me. It watches Jenkins, finds the failure, runs deterministic checks before touching any LLM, posts the analysis to a web UI, and waits for me to click a button before doing anything.

Here's what actually mattered.

---

## The 90% token reduction that made this actually useful

The first thing I tried was dumping the entire build log into an LLM prompt. 10,000 tokens per failure. Results were slow, expensive, and often wrong — the model kept fixating on warning messages from passing stages.

The fix was obvious in retrospect: only send the failed stage.

Jenkins logs have clear boundaries: `[Pipeline] stage (Docker Build)`. I parse these, find the stage containing the error, extract just that block, and cap the whole context at 1000 tokens. The log cleaner strips ANSI codes, timestamps, `[INFO]` prefixes, and progress bars.

What goes to the LLM is about 550 tokens of actual signal. The model does noticeably better with it.

---

## Deterministic verification first, LLM second

This was the other big lesson.

A common Jenkins failure is a tool name mismatch. The Jenkinsfile says `maven 'Maven3'` but Global Tool Configuration has it as `Maven-3`. The pipeline fails with a cryptic error. An LLM will hallucinate an explanation.

I wrote a crawler that parses the `tools {}` block from the Jenkinsfile, queries the Jenkins API for configured global tools, and does exact match followed by Levenshtein fuzzy match at 0.85 threshold. If it finds a mismatch, it flags it before the LLM sees anything.

The verification report goes into the LLM prompt alongside the log. The model gets facts, not raw noise. It stops hallucinating tool configuration issues because I've already determined whether there is one.

There's one more thing the context builder adds: the actual Groovy source for the failing stage. Not just the error output — the `stage('Build') { ... }` block itself. That gives the LLM ground truth about what the Jenkinsfile says, so it can spot typos and wrong step names directly instead of guessing from stack traces.

---

## Architecture

<!-- ADD ARCHITECTURE DIAGRAM IMAGE HERE -->

Six modules in sequence:

- **Parser** — receives the webhook payload, identifies which stage failed, pulls that stage's logs, strips ANSI codes and timestamps and INFO lines
- **Verification crawler** — parses Jenkinsfile tool references and credential IDs, queries Jenkins API to check against Global Tool Configuration, plugin manager, and credentials store
- **Context builder** — assembles a 1000-token payload: metadata, verification findings, failing stage Groovy source, cleaned log
- **Analyzer** — calls the LLM, caches responses by MD5 hash of the context
- **Agent** — maps the LLM's recommendation to a concrete executor; tool mismatches and missing credentials are always diagnostic-only
- **Web UI** — shows analysis, proposed fix, confidence score; Approve or Reject before anything runs

No component knows about the others. The LLM is one node in the chain, not the coordinator.

---

## Why I kept humans in the loop

I thought about auto-fixing things. The temptation is real — if confidence is high and the fix is a simple retry, why wait for a button click?

Three reasons I didn't:

**Trust.** The system is new. I want to watch what it recommends before letting it act. Even a 90% accurate auto-fix will damage something eventually, and I'd rather see it coming.

**Scope.** Some fixes are never safe to automate — tool name mismatches, missing credentials, IAM issues. These need a human to touch the configuration. The system flags them as "diagnostic only" with no action button.

**Audit trail.** Every approved fix writes to an append-only JSONL log: timestamp, fix type, job name, build number, confidence score. No secret values, ever.

---

## What's auto-fixable and what isn't

**Auto-fixable (with approval):**
- Retry the pipeline
- Clear Docker, npm, pip, or Maven cache
- Pull a fresh image
- Increase stage timeout

**Never auto-fixed — always diagnostic:**
- Tool name mismatches
- Missing plugins
- Missing credentials
- IAM issues

The logic is simple. The first group is safe to retry — worst case it fails again. The second group has too many ways to make things worse. Wrong credentials, wrong permissions, wrong tool version. Better to surface exactly what's wrong and let a human fix it intentionally.

---

## The token math

Full log to LLM: ~10,000 tokens. At Haiku pricing that's around $0.03 per failure.

Selective context: ~1,000 tokens. That's around $0.003 per failure.

With response caching on repeat failures, production cost works out to around $0.01/month. The 90% reduction isn't theoretical — it's what happens when you stop sending passing stage logs to an LLM.

---

## Running it locally on an M4

I have a 32GB M4 MacBook Air. `llama3.1:8b` handles analysis tasks. `qwen2.5-coder:32b` handles generation (Jenkinsfile Copilot mode).

Switching to Anthropic is one `.env` change:

```
LLM_PROVIDER=anthropic
```

No code changes. The provider abstraction layer handles routing — Haiku for analysis, Sonnet for generation, same interface throughout. I learned the lesson that model routing decisions should live in config, not scattered across function calls, about two weeks in.

---

## Copilot mode

The reactive side (failure → fix) was the main goal. But I added a second mode: generate pipelines from natural language.

Type a description in the web UI chat — "build a Docker image, push to ECR, deploy to ECS" — and the system picks a base Jenkinsfile template, sends it to the LLM with your request, validates the output (brace balance, required Declarative Pipeline keywords), retries once with a correction prompt if it fails, then shows you the result. Approve and it creates or updates the Jenkins job via API.

---

## What I'd do differently

**Start with the verification crawler.** I built the LLM integration first and spent a week confused about why the model kept getting tool names wrong. The crawler should have come first.

**Response caching.** Same failure, same log, same verification result — hits the MD5 cache instead of calling the LLM again. It's implemented. I haven't seen it fire much in practice because my failures aren't repetitive enough, but it matters at scale.

**Test isolation.** 152 tests, none requiring live Jenkins, GitHub, or LLM. Everything is mocked at the boundary. This made the whole thing buildable without external accounts until late in development. Worth the setup cost upfront.

---

## What's still missing (honest)

- GitHub Actions crawler — verification is Jenkins-only right now
- GitHub repo committer — Copilot mode creates Jenkins jobs but can't commit workflow YAML to a repo
- Secrets manager — currently a thin audit stub, not a real write to Jenkins credentials store or GitHub secrets API
- Redis cache — it's in docker-compose, commented out; cache is in-memory for now

The reactive pipeline (webhook → analyze → approve → fix) works end to end. These are next.

---

## Numbers

- Token reduction: ~10,000 tokens → ~1,000 tokens per failure analysis
- Test suite: 152 tests, 0 requiring live external services
- LLM cost in testing: ~$0.015 total (Anthropic free credits)
- Providers supported: Ollama (local), Anthropic

---

## The code

Repo goes public after Phase 6 cleanup: [github.com/adil-khan-723/cicd-ai-copilot](https://github.com/adil-khan-723/cicd-ai-copilot). Questions meanwhile: adilk81054@gmail.com or [dev.to/adil-khan-723](https://dev.to/adil-khan-723).

If you're building something similar, the part worth stealing is the verification-before-LLM pattern. The model does much better when it's given facts about your specific configuration rather than raw log output.
