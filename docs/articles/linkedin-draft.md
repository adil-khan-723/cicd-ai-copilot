# LinkedIn post draft

---

I spent the last month building an AI agent that watches my CI/CD pipelines, analyzes failures, and waits for me to approve a fix before it does anything.

The part that made it actually work: don't send the full log to the LLM.

A typical build log is 10,000+ tokens. Most of it is passing stages. The model fixates on warning messages from code that ran fine. I cut it down to just the failed stage — ~550 tokens — and the analysis got noticeably better.

The second thing: run deterministic checks before the LLM sees anything. A lot of Jenkins failures are tool name mismatches. The Jenkinsfile says `Maven3`, the global config says `Maven-3`. Rather than letting the model guess, I wrote a crawler that parses the Jenkinsfile, queries the Jenkins API, and flags the mismatch directly. The LLM gets a fact, not a log to interpret.

What the system does end to end:

- Webhook receives the failure event
- Parser finds the failed stage
- Log cleaner strips ANSI, timestamps, noise
- Verification crawler checks config against Jenkins/GitHub APIs
- Context builder packs everything into ~850 tokens
- LLM analyzes it (Ollama locally, or Anthropic via .env swap)
- Slack message with root cause, suggested fix, confidence %
- Buttons: Apply Fix, Manual Review, Dismiss
- Fix executor calls Jenkins API only after approval
- Audit log records who approved what, when

Tool mismatches, missing credentials, IAM issues — those never get an "Apply Fix" button. Some things need a human to touch the config.

There's also a Copilot mode: `/devops generate jenkins python docker ecr` generates a Jenkinsfile from a base template, shows a 20-line preview in Slack, and commits to GitHub on approval.

Runs fully locally on my M4 MacBook Air (32GB) with Ollama. Switch to Anthropic with one `.env` change, no code changes.

163 tests. 6 phases. 37 increments.

Code: github.com/adil-khan-723/cicd-ai-copilot

Full writeup on Dev.to (link in comments).

---

*Suggested image: architecture diagram or Slack screenshot of the failure alert with buttons*
