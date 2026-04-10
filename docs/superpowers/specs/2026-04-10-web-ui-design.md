# Web UI Design Spec
**Date:** 2026-04-10  
**Project:** DevOps AI Agent — CI/CD Copilot & Auto-Remediation System  
**Replaces:** Slack as primary interface  

---

## Overview

Replace Slack as the primary UI with a self-hosted web dashboard. Slack remains as an optional out-of-band fallback for critical system alerts. The web UI shows the full pipeline event feed in real time, hosts the agent chat for pipeline generation and questions, and handles fix approvals.

**Single deliverable:** A FastAPI-served dashboard at `http://localhost:8000` (same port as the existing webhook server). No separate frontend process, no build step, no npm.

---

## Architecture

### Approach: Single FastAPI app

The existing `webhook/server.py` gains three new routes. A new `ui/` module handles them. No new processes.

```
GET  /                → serves ui/static/index.html
GET  /events          → SSE stream of pipeline events
POST /api/chat        → agent chat (LLM, streams response)
POST /api/fix         → execute approved fix
POST /api/commit      → commit generated file to GitHub + apply to Jenkins
POST /api/setup       → save GitHub/Jenkins credentials to .env on first run
```

### New module: `ui/`

```
ui/
  __init__.py
  routes.py          — FastAPI router, mounts all 6 routes above
  event_bus.py       — in-memory pub/sub; pipeline stages publish, SSE subscribes
  chat_handler.py    — receives user message, routes to LLM, streams tokens back
  setup_handler.py   — validates and writes credentials to .env
  static/
    index.html       — entire dashboard (single HTML file, self-contained)
    app.js           — SSE client + chat + fix approval logic (~200 lines vanilla JS)
```

### Integration point

Every stage in `_process_failure_sync` (in `webhook/server.py`) calls `event_bus.publish(event)` after completing. The SSE endpoint streams these to all connected browsers.

---

## First-Run Setup Wizard

**Trigger:** On first launch, if `GITHUB_TOKEN` or `JENKINS_TOKEN` is missing from `.env`, the dashboard renders the setup overlay on top of the (empty) dashboard.

**Fields collected:**

| Field | `.env` key | Validation |
|---|---|---|
| GitHub repo (owner/repo) | `GITHUB_REPO` | regex `^[\w.-]+/[\w.-]+$` |
| GitHub PAT | `GITHUB_TOKEN` | must start with `ghp_` or `github_pat_` |
| Jenkins URL | `JENKINS_URL` | must be valid URL |
| Jenkins username | `JENKINS_USER` | non-empty |
| Jenkins API token | `JENKINS_TOKEN` | non-empty |

On submit: `POST /api/setup` validates each field, writes to `.env`, and returns `{"ok": true}`. The browser dismisses the overlay and the dashboard becomes live.

**"New Project" button** in the topbar re-opens the setup overlay. Submitting overwrites the current `.env` values. This lets Adil switch GitHub repos when starting a new job without touching any files.

Credentials are written to `.env` only. Never logged, never sent anywhere else.

---

## Topbar

Left to right:
- **Logo** — `⚡ devops-ai`
- **Active repo chip** — `owner/repo ↗` (links to GitHub). Clicking reopens the setup wizard.
- **+ new project button** — reopens setup wizard
- **Stats** — Jenkins status · active failures count · LLM model name · fixes applied today
- **Agent status pill** — `agent running` with pulsing green dot (or `agent stopped` in red if the process is down)

---

## Left Panel — Pipeline Runs Feed

Width: 420px fixed. Scrollable list of build cards, newest first.

### Build card

Each card shows one Jenkins/GitHub Actions build run.

**Header row:** colored dot (red=failure, green=success/fixed, yellow=running) · job name · build number · status label · timestamp

**Stage graph** (horizontal):  
Nodes connected by lines. Each node = one pipeline stage.  
- Green circle ✓ = passed  
- Red circle ✗ = failed (the stage where execution stopped)  
- Grey `–` = not reached (skipped because upstream failed)  
- Yellow pulsing = currently running  

The line between nodes takes the color of the left node (green if that stage passed, red if it failed).

**Incremental log** (only on active/failure cards):  
A scrolling terminal window showing lines from each stage in order as they arrive via SSE. Passed stages show their last output line in green. The failed stage shows the full error output. The final line is the LLM analysis result, appended once analysis completes, with a blinking cursor while streaming.

**Fix actions:**  
- If `fix_type` is auto-fixable and confidence ≥ 0.75: `[Apply Fix · <fix_type>]` + `[Dismiss]`  
- If diagnostic only (IAM, missing plugin, tool mismatch): `[Manual review required — <reason>]`  
- After fix applied: card dims, status updates to `FIX_APPLIED`, stage graph updates if re-run succeeds

**Collapsed state:** Resolved cards (fix applied, dismissed, or clean success) collapse to header + stage graph only. Opacity 40–55% to de-emphasize.

---

## Right Panel — Agent Chat

**System event markers:** Between messages, inline system events show what's happening: `→ template selected · python-docker-ecr.groovy · generating via qwen2.5-coder:14b`

**Message bubbles:**  
- Agent messages: dark background, left-aligned, `AI` avatar  
- User messages: slightly lighter background, right-aligned, `A` avatar  
- Code blocks: dark background, left cyan border, JetBrains Mono, syntax-highlighted (keywords in purple, strings in green, comments in dim)

**Approve & Commit button** (appears on generated pipeline messages):  
Single button: `Approve & Commit + Apply to Jenkins`  
This triggers `POST /api/commit` which:  
1. Commits the file to `GITHUB_REPO` via PyGithub (`Jenkinsfile` at repo root, or `.github/workflows/ci.yml` for GH Actions)  
2. Creates/updates the Jenkins job via python-jenkins  
3. Posts a system event to the chat: `✓ committed to adil-khan-723/build-api · Jenkins job updated`

**LLM streaming:** Agent responses stream token by token. The JS `fetch` with `ReadableStream` consumes the chunked response and appends to the bubble as tokens arrive.

**Input:**  
- `›` prompt prefix  
- Placeholder: `generate pipeline · explain failure · add lint stage · list templates`  
- `↑` send button  
- Hint line: `agent mode: copilot · local inference · no external apis`

---

## Real-Time Updates (SSE)

**Endpoint:** `GET /events` — returns `text/event-stream`, stays open.

**Event schema:**
```json
{
  "type": "step | fix_result | chat_token | system",
  "job": "build-api",
  "build": 42,
  "stage": "LOG_EXTRACTED",
  "detail": "284 lines → 38 lines (failed stage only)",
  "ts": "2026-04-10T14:31:02Z",
  "status": "done | fail | running"
}
```

The browser `EventSource` listener matches `type` and:
- `step` → appends to the correct build card's log and updates stage graph node
- `fix_result` → updates the card's action buttons and status
- `chat_token` → appends to the current agent bubble
- `system` → inserts a system event marker in the chat

**Reconnection:** `EventSource` auto-reconnects on disconnect. The server sends a `retry: 3000` directive.

---

## Slack Fallback

Controlled by `SLACK_ALERTS=enabled|disabled` in `.env` (default: `enabled` to not break existing setups).

- `disabled` → all output goes to web UI only  
- `enabled` → Slack DM gets failure alerts in parallel (existing behavior preserved)

**Always goes to Slack regardless of flag:**  
- LLM provider unavailable (all providers in fallback chain failed)  
- Webhook server startup failure  
- Jenkins unreachable for >3 consecutive webhooks  

These are the moments the browser tab is most likely closed.

---

## Visual Design

**Font stack:** JetBrains Mono (code, labels, stats) + Inter (body text, descriptions)

**Color palette:**
| Role | Value |
|---|---|
| Background | `#0a0d14` |
| Panel bg | `#0f1520` |
| Card bg | `#141b2d` |
| Border | `#1e2d40` |
| Text primary | `#cbd5e1` |
| Text secondary | `#94a3b8` |
| Text dim | `#3d5570` |
| Accent cyan | `#38bdf8` |
| Success green | `#34d399` |
| Failure red | `#f87171` |
| Warning yellow | `#fbbf24` |
| Purple (keywords) | `#a78bfa` |

No scanlines. No glow effects. Borders are solid, not glowing. Color is used for meaning (green=pass, red=fail, cyan=interactive), not decoration.

---

## What Is Not Changing

- `webhook/server.py` — same endpoint, same signature validation, same `_process_failure_sync` pipeline. Only addition: `event_bus.publish()` calls between stages.
- `agent/`, `analyzer/`, `parser/`, `verification/`, `copilot/` — untouched.
- `slack/` — stays. `SLACK_ALERTS=disabled` switches it off; the module is not deleted.
- Docker Compose — add `ui/static/` as a volume mount so the HTML can be updated without rebuilding the container.

---

## Resume / Interview Notes

- **SSE over WebSocket** — deliberate. The failures feed is read-only push; full duplex (WebSocket) would be overengineering. SSE is a standard HTTP feature with native `EventSource` browser support.
- **No React** — the impressive engineering is in the backend (LLM routing, deterministic verification, 90% token reduction). A vanilla JS frontend keeps the architecture story clean and removes a build pipeline with zero benefit.
- **Single process** — web UI, webhook receiver, and agent all run in one FastAPI process. No nginx, no separate frontend server. `docker-compose up` and it's done.
- **First-run wizard** — shows understanding of real-world deployment: nobody wants to hand-edit `.env` files for every new job or client.
