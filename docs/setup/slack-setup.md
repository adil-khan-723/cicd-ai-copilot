# Slack App Setup — From Scratch

This guide sets up the Slack workspace and app needed for the DevOps AI Agent.
Complete this before running any code that touches Slack.

---

## Step 1 — Create or Choose a Slack Workspace

Option A — Use an existing workspace you control.  
Option B — Create a free workspace at https://slack.com/create

Recommended: create a dedicated workspace (e.g. "devops-agent-dev") to avoid
spamming a real team workspace during development.

---

## Step 2 — Create the Slack App

1. Go to https://api.slack.com/apps
2. Click **Create New App**
3. Select **From an app manifest**
4. Choose your workspace
5. Paste the manifest below (YAML format), then click **Next** → **Create**

### App Manifest

```yaml
display_information:
  name: DevOps AI Agent
  description: CI/CD failure analyzer and pipeline copilot
  background_color: "#1a1a2e"

features:
  bot_user:
    display_name: devops-agent
    always_online: true
  slash_commands:
    - command: /devops
      description: Generate pipelines or get CI/CD help
      usage_hint: "generate jenkins <description>"
      should_escape: false

oauth_config:
  scopes:
    bot:
      - chat:write
      - chat:write.public
      - commands
      - im:write
      - users:read

settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.im
  interactivity:
    is_enabled: true
  socket_mode_enabled: true
  token_rotation_enabled: false
```

---

## Step 3 — Enable Socket Mode (for local development)

Socket Mode lets your local app receive events without exposing a public URL.
No ngrok needed during development.

1. In your app settings → **Socket Mode** → Toggle **Enable Socket Mode** ON
2. Give the app-level token a name (e.g. `devops-agent-local`)
3. Add scope: `connections:write`
4. Click **Generate** → copy the `xapp-...` token

---

## Step 4 — Install App to Workspace

1. Go to **OAuth & Permissions** in your app settings
2. Click **Install to Workspace**
3. Authorize the app
4. Copy the **Bot User OAuth Token** (`xoxb-...`)

---

## Step 5 — Get the Signing Secret

1. Go to **Basic Information** → **App Credentials**
2. Copy the **Signing Secret**

---

## Step 6 — Update .env

```bash
SLACK_BOT_TOKEN=xoxb-...         # from Step 4
SLACK_APP_TOKEN=xapp-...         # from Step 3
SLACK_SIGNING_SECRET=...         # from Step 5
SLACK_CHANNEL=#devops-alerts
```

---

## Step 7 — Create the Alert Channel and Invite Bot

```
In Slack:
1. Create channel: #devops-alerts
2. Type: /invite @devops-agent
```

---

## Step 8 — Verify

```bash
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     https://slack.com/api/auth.test
```

Expected response:
```json
{
  "ok": true,
  "team": "Your Workspace",
  "user": "devops-agent",
  "bot_id": "B..."
}
```

---

## Interactivity Endpoint (set in Phase 3)

When you deploy the webhook server (Increment 6), update:

- **Interactivity & Shortcuts** → Request URL: `https://your-host/slack/events`
- **Event Subscriptions** → Request URL: same

For local dev with Socket Mode enabled, these URLs are not required.

---

## Slack App Permissions Summary

| Scope | Used for |
|---|---|
| `chat:write` | Post failure alerts to channels |
| `chat:write.public` | Post to channels bot isn't member of |
| `commands` | Handle `/devops` slash command |
| `im:write` | Send DMs (secrets manager — Phase 5) |
| `users:read` | Identify who clicked approval buttons |
