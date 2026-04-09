# Building a human-in-the-loop AI agent for CI/CD failure recovery

---

*tags: devops, ai, cicd, python*

---

My pipelines break every week. Usually Docker cache issues, sometimes a pip dependency conflict, occasionally a missing credential that someone rotated and forgot to update. Each one takes 20-40 minutes to diagnose. Most of that time is spent opening logs, figuring out which stage failed, cross-checking job config, then deciding what to actually fix.

I built a tool that does most of that for me. It watches Jenkins and GitHub Actions, finds the failure, runs deterministic checks before touching any LLM, posts the analysis to Slack, and waits for me to click a button before doing anything.

Here's what actually mattered.

---

## The 90% token reduction that made this actually useful

The first thing I tried was dumping the entire build log into an LLM prompt. 10,000 tokens per failure. Results were slow, expensive, and often wrong — the model kept fixating on warning messages from passing stages.

The fix was obvious in retrospect: only send the failed stage.

Jenkins logs have clear boundaries: `[Pipeline] stage (Docker Build)`. GitHub Actions has `##[group]` markers. I parse these, find the stage containing the error keyword, extract just that block, and cap it at 2,000 characters. Then the log cleaner strips ANSI codes, timestamps, `[INFO]` prefixes, and progress bars.

What goes to the LLM is about 550 tokens of actual signal. The model does noticeably better with it.

---

## Deterministic verification first, LLM second

This was the other big lesson.

A common Jenkins failure is a tool name mismatch. The Jenkinsfile says `maven 'Maven3'` but the Global Tool Configuration has it as `Maven-3`. The pipeline fails with a cryptic error. An LLM will hallucinate an explanation.

I wrote a crawler that parses the `tools {}` block from the Jenkinsfile, queries the Jenkins API for configured global tools, and does exact match followed by Levenshtein fuzzy match (threshold 0.85). If it finds a mismatch, it flags it before the LLM sees anything.

Same thing for GitHub Actions: extract all `${{ secrets.X }}` references, compare against the GitHub API's secrets list, flag anything missing. Check runner labels. Warn on unpinned `@main` actions.

The verification report goes into the LLM prompt alongside the log. The model gets facts, not raw noise. It stops hallucinating tool configuration issues because I've already determined whether there is one.

---

## Why I kept humans in the loop

I thought about auto-fixing things. The temptation is real — if confidence is high and the fix is a simple retry, why wait for a button click?

Three reasons I didn't:

**Trust.** The system is new. I want to watch what it recommends before letting it act. Even a 90% accurate auto-fix will damage something eventually, and I'd rather see it coming.

**Scope.** Some fixes are never safe to automate — tool name mismatches, missing credentials, IAM issues. These need a human to touch the configuration. The system flags them with a "diagnostic only" label and no action button.

**Audit trail.** Every approved fix writes to an append-only JSONL log: timestamp, fix type, job name, build number, who clicked the button, confidence score. No secret values, ever.

The Slack message has two states. Initial: the failure details and log excerpt, "Analysis pending...". After the LLM runs: root cause, suggested fix, confidence percentage, and buttons — "Apply Fix" or "Dismiss" when confidence clears the threshold, "Manual Review" when it doesn't.

---

## The architecture in one paragraph

Webhook server (FastAPI) receives the failure event. Pipeline parser finds the failed stage. Log extractor pulls just that block. Log cleaner strips the noise. Verification crawler checks Jenkins/GitHub config against the API. Context builder packs everything into ~850 tokens. LLM analyzer calls whichever provider is configured (Ollama locally, or Anthropic/Groq/Gemini via `.env` swap). Response parser extracts JSON. Slack notifier posts the alert. Approval handler waits for a button click. Fix executor calls the Jenkins API. Audit log records the result.

No component knows about the others. The LLM is one node in the chain, not the coordinator.

---

## Running it locally on an M4

I have a 32GB M4 MacBook Air with a 2TB external SSD. `llama3.1:8b` runs analysis tasks. `qwen2.5-coder:14b` handles generation (Jenkinsfiles, GitHub Actions YAML).

The models live on the SSD so they don't eat internal storage. I use a custom launchd plist instead of Homebrew's service, because `brew services restart ollama` regenerates the plist and wipes any manual edits to `OLLAMA_MODELS`. Learned that the hard way.

Switching to Anthropic is one `.env` change:

```
LLM_PROVIDER=anthropic
```

No code changes. The provider abstraction layer handles routing — Haiku for analysis, Sonnet for generation, same interface.

---

## Copilot mode

The reactive side (failure → fix) was the main goal. But I added a second mode: generate pipelines from natural language.

`/devops generate jenkins python docker ecr build push` in Slack kicks off a generation flow. The system picks the closest base template (there are six: three Jenkins, three GitHub Actions), sends it to the LLM with the request, validates the output (brace balance for Groovy, PyYAML parse for YAML), retries once with a correction prompt if it fails, then posts a 20-line preview with "Approve & Commit" and "Cancel" buttons.

Approve commits the file to GitHub directly. For Jenkins, it also creates or updates the job via the Jenkins API.

The template selector tokenizes the request, scores each template against keyword overlap, and picks the most specific match. "node.js docker build" correctly routes to the Node template, not Python — that took an actual fix because "node.js" doesn't split cleanly on spaces.

---

## What I'd do differently

**Response caching.** Same failure, same log, same verification result — hits the MD5 cache instead of calling the LLM again. I implemented it. I haven't seen it fire in practice because my failures aren't that repetitive.

**The provider fallback chain.** I built it. Ollama → Groq on failure. In reality Ollama has never been down when I needed it, so the fallback is untested in production.

**Test coverage.** 163 tests. None of them require a live Jenkins, GitHub, Slack, or LLM. Everything is mocked. This made the whole thing buildable without any external accounts until late in the process.

**Webhook validation.** The HMAC check is there for Jenkins and GitHub. In local dev I skip it. That's fine for local dev. Don't skip it in production.

---

## Numbers

- Token reduction: ~10,000 tokens → ~850 tokens per failure analysis
- Test suite: 163 tests, 0 requiring live external services
- LLM cost in testing: ~$0.015 total (Anthropic free credits)
- Providers supported: Ollama (local), Anthropic, Groq, Gemini

---

## The code

Everything is on GitHub: [adil-khan-723/cicd-ai-copilot](https://github.com/adil-khan-723/cicd-ai-copilot)

Six phases, 37 increments, each merged as a separate PR. The commit history is a build log for the project itself.

If you're building something similar, the part worth stealing is the verification-before-LLM pattern. The model does much better when it's given facts about your specific configuration rather than raw log output.
