# User Guide

End-user walkthrough for the DevOps AI Agent. Covers first-time setup, day-to-day use, and the most common troubleshooting paths.

For architecture and design rationale, see [README.md](README.md).

---

## Table of Contents

1. [First-Time Setup](#first-time-setup)
2. [Web UI Tour](#web-ui-tour)
3. [Settings Reference](#settings-reference)
4. [Daily Workflow](#daily-workflow)
5. [Troubleshooting](#troubleshooting)

---

## First-Time Setup

### 1. Boot the agent

```bash
git clone <repo> && cd PlatformTool
./start.sh
```

`start.sh` handles Python install (via `uv` if needed), venv setup, dependency install, frontend build, and starts the FastAPI server on port 8000.

Open `http://localhost:8000` in a browser.

### 2. Configure Jenkins (one-time per Jenkins instance)

In the **setup wizard** that appears on first load:

| Field | What |
|---|---|
| Profile name | Friendly label (e.g. "Production", "Staging") |
| Jenkins URL | `http://your-jenkins-host:8080` |
| Auth method | API Token (recommended) or Password |
| Username | Jenkins username |
| API Token / Password | Secret value |

Click **"Test Connection"** to verify before saving. Status messages distinguish auth failure (401/403), wrong endpoint (404), connection timeout, and show Jenkins version on success.

When you click **Save**, the agent automatically:

1. **Installs required Jenkins plugins** (`notification` + `junit` — junit is a hard runtime dep of the notification plugin's `getTestResults()` and silently breaks webhooks if missing)
2. **Configures every existing job's notification endpoint** to POST failures back to this agent
3. **Sets correct `event=all` + `branch=.*`** fields (legacy plugin requires both populated to actually fire — wrong/missing values cause silent skip)

If plugins were newly installed, **restart Jenkins** for them to take full effect (Manage Jenkins → Restart).

### 3. Configure LLM provider

Settings panel → **LLM Configuration**:

- **Anthropic (cloud)**: Save your API key, pick analysis + generation models from the dropdown (Haiku 4.5 / Sonnet 4.6 / Opus 4.7)
- **Ollama (local)**: Set Ollama URL + single model name (mirrors to both analysis + generation env keys)

Click **"Test Connection"** to verify the key/connection works before saving.

API keys are stored in the multi-key manager — see [Multi-Key API Manager](#multi-key-api-manager) below.

### 4. (Optional) Set PUBLIC_BASE_URL when Jenkins is on a different host

If Jenkins is at `http://13.127.185.174:8080` and the agent is at `http://13.201.3.80:8000`, the agent needs to know its own public URL so Jenkins can call back. Set in `.env`:

```env
PUBLIC_BASE_URL=http://13.201.3.80:8000
```

If you skip this, the agent guesses from the browser's request URL — works when Jenkins can reach you on the same hostname your browser uses.

---

## Web UI Tour

### Feed (default view)
Live SSE stream of pipeline events. Each failure appears as a card with:
- **Root cause** + LLM model badge (🧠/🦙) + 🔑 key name (cost attribution)
- **Suggested fix** with confidence
- **Action buttons**: Apply Fix / Re-analyze / Dismiss / View Logs

### Re-analyze with a different model
Each card has a **Re-analyze with…** dropdown. Pick a different provider/model, click Re-run. The override is one-shot (bypasses cache, doesn't change global settings). Card updates in place with `↻` next to the new model badge.

### Settings panel
Configure profiles, API keys, LLM provider, view audit log, run Jenkins auto-setup.

### Copilot chat
Generate Jenkinsfiles from natural language. Examples:
- `generate jenkins python-docker-ecr`
- `generate jenkins node-build-and-test`

Output previews in chat with syntax highlighting; commit applies via Jenkins API.

---

## Settings Reference

### Multi-profile Jenkins management
Save credentials for multiple Jenkins instances. Switching the active profile:
- Rewrites `.env` with new credentials
- Hot-reloads settings (no server restart)
- Clears the SSE feed so cards from another profile don't bleed in
- Triggers Jenkins auto-setup in the background for the new instance

Per-profile chat history persists in browser localStorage keyed on `profile.id`. Re-running the setup wizard with the same Jenkins URL+user is **idempotent** — the same profile id is reused, chats survive.

### Multi-Key API Manager
Manage multiple API keys per provider. Each key has:
- **Name** (`work`, `personal`, `client-X`)
- **Provider** tag (Anthropic, more later)
- **Active flag** (one active per provider — feeds `.env`)

Operations:
- **Add Key**: First key per provider auto-activates
- **Activate**: Switches active key, writes to `.env`, hot-reloads — no restart
- **Delete**: Inactive keys delete instantly. Active keys trigger a **switch-then-delete** confirmation: pick a replacement → activate it → delete the old. Prevents accidental loss of LLM access.

Per-analysis tracking: `analysis_complete` events stamp the active `key_name`. BuildCard shows 🔑 badge with the name so you can see which key produced each analysis.

### LLM Configuration
- **Anthropic dropdowns** locked to known models (typo-proof). Legacy/unknown saved values surface as `(legacy)` so they're not silently discarded.
- **Ollama** uses a single text field that mirrors to both `analysis_model` and `generation_model` env keys.

### Jenkins Webhook Setup
Manual re-run of the auto-config that runs on profile activate. Useful when:
- You add new jobs in Jenkins (re-run to configure them)
- Jenkins admin removed the notification plugin (re-run to reinstall)
- You changed `PUBLIC_BASE_URL`

Reports show: plugins installed/already-present, jobs configured/already-configured, errors, restart-required flag.

---

## Daily Workflow

1. Pipeline fails in Jenkins
2. Within seconds (notification plugin) or up to 30s (failure poller fallback), a card appears in the agent's Feed
3. Read root cause + suggested fix
4. Click **Apply Fix** if confident, or **Re-analyze** with a beefier model (Opus 4.7), or **Dismiss** if false-positive
5. After Apply: Jenkinsfile patched in Jenkins config, build retriggered automatically
6. Watch new build's outcome — success card appears, prompts to discard the failure card

---

## Troubleshooting

### "All LLM providers unavailable"
- Settings → LLM Configuration shows your provider + masked key
- If saved key is empty, add via API Keys card
- If key shown but errors persist, click **Test Connection** in LLM Configuration — surfaces auth errors directly from Anthropic
- Check Settings → LLM Status section for live availability per provider

### Jenkins builds fail but no card appears in feed
1. Check Settings → Jenkins Webhook Setup → run "Configure Jenkins for Webhooks" — it'll report whether plugins are installed and jobs are configured
2. If plugins were just installed, **restart Jenkins** (Manage Jenkins → Restart). Fresh-installed plugins don't fully wire their RunListener until restart.
3. Verify Jenkins can reach your agent: from Jenkins host run `curl http://your-agent:8000/health` — should return `{"status": "ok"}`. If it fails, check AWS Security Group / firewall.
4. If notification plugin is broken anyway, the **30s poller** still picks up failures. Check server logs for `Poller detected new failure: ...`.

### Webhook silently drops every notification (advanced)
Notification Plugin v1.18 has three known silent failure modes (PR #53 auto-fixes all):
- Missing `junit` plugin → `NoClassDefFoundError` inside `getTestResults()`
- `<event>` field set to a phase name (`finalized`/`started`) instead of `all`/`failed`/etc
- `<branch>` null when job has no SCM trigger (BRANCH_NAME env var absent)

Force-fire test via Jenkins script console:
```groovy
import com.tikal.hudson.plugins.notification.*
def job = jenkins.model.Jenkins.instance.getItemByFullName("YOUR-JOB-NAME")
def baos = new java.io.ByteArrayOutputStream()
def listener = new hudson.util.StreamTaskListener(new java.io.PrintStream(baos))
Phase.FINALIZED.handle(job.lastBuild, listener, System.currentTimeMillis())
println new String(baos.toByteArray())
```
Output reveals the silent skip reason ("Environment does not contain BRANCH_NAME", `NoClassDefFoundError`, etc).

### Chat history disappeared
Chat is stored in browser localStorage keyed on `profile.id`. If you re-saved credentials BEFORE PR #49 (idempotent profile add), each save generated a new `profile.id` → orphaned chats under stale keys. Look in browser DevTools → Application → Local Storage for keys matching `devops_ai_chats:*`. Newer profile saves now reuse the same id.

### Server won't start
- `ANTHROPIC_API_KEY not set` warning is now non-fatal (PR #46) — server boots, configure key via Settings UI
- Port 8000 in use → `WEBHOOK_PORT=8001` in `.env`

### Keys stored where?
- `.env` holds the **active** key per provider (read by pydantic-settings)
- `$DATA_DIR/llm_keys.json` (default `~/.devops-ai/llm_keys.json`) holds **all** keys with metadata
- Test endpoint never logs keys; key values masked in API responses (`sk-ant-…abcd`)
