# LinkedIn post draft

---

I've been dealing with the same pipeline failures for months. Docker cache, pip conflicts, a credential someone rotated and forgot to update. Each one kills 20-40 minutes just figuring out what broke.

So I built something that does that part.

It watches Jenkins, finds the failure, and shows me the analysis in a web UI — root cause, suggested fix, confidence score. Two buttons: Approve or Reject. Nothing touches Jenkins until I click.

Two things made it actually work:

Sending only the failed stage to the LLM, not the full log. A typical build log is 10,000+ tokens, most of it from stages that ran fine. Cutting it to ~550 tokens of actual signal made the analysis useful.

Verifying tool names before the LLM sees anything. Jenkinsfile says `Maven3`, global config has `Maven-3` — a model will hallucinate an explanation for that. I crawl the Jenkins API first and give the model facts, not logs to interpret.

Tool mismatches and missing credentials never get an approve button. Those need a human to fix the config. Everything else — retry, clear cache, pull a fresh image — runs after I click.

Runs locally on my M4 with Ollama. One `.env` change for Anthropic. 152 tests.

Full writeup: https://dev.to/adil-khan-723/building-a-human-in-the-loop-ai-agent-for-cicd-failure-recovery-15pd

Repo: https://github.com/adil-khan-723/cicd-ai-copilot

---

*Suggested image: architecture diagram or web UI screenshot showing the failure alert with Approve/Reject buttons*
