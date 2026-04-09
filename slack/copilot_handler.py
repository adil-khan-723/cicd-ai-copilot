"""
Slack Copilot handler (Increments 25 + 26).

Handles:
  /devops generate jenkins <description>
  /devops generate github <description>
  /devops generate jenkins list
  /devops generate github list

And button actions:
  copilot_approve  → commit file to GitHub repo
  copilot_cancel   → cancel, update message
"""
import logging
from slack_bolt import App
from slack_sdk import WebClient

from config import get_settings
from copilot.pipeline_generator import generate_jenkinsfile
from copilot.actions_generator import generate_workflow
from copilot.template_selector import list_templates
from copilot.repo_committer import commit_pipeline_file
from slack.copilot_message_templates import (
    pipeline_preview_blocks,
    pipeline_committed_blocks,
    pipeline_cancelled_blocks,
)

logger = logging.getLogger(__name__)

# In-memory store mapping message_ts → generated content for approval
# {ts: {"platform": str, "content": str, "template_name": str, "request": str}}
_pending_generations: dict[str, dict] = {}


def register_copilot_handlers(app: App) -> None:
    """Register slash command and button handlers for Copilot mode."""

    @app.command("/devops")
    def handle_devops_command(ack, command, client: WebClient, logger=logger):
        ack()

        text = (command.get("text") or "").strip()
        user_id = command["user_id"]
        channel_id = command["channel_id"]

        parts = text.split(None, 2)  # ["generate", "jenkins"|"github", "description..."]

        if not parts or parts[0].lower() != "generate":
            _post_help(client, channel_id, user_id)
            return

        if len(parts) < 2:
            _post_help(client, channel_id, user_id)
            return

        platform = parts[1].lower()
        if platform not in ("jenkins", "github"):
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"Unknown platform '{platform}'. Use `jenkins` or `github`.",
            )
            return

        description = parts[2] if len(parts) > 2 else ""

        # Handle 'list' sub-command
        if description.strip().lower() == "list" or not description:
            _post_template_list(client, channel_id, user_id, platform)
            return

        # Post "Generating..." ephemeral first (immediate feedback)
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f":hourglass_flowing_sand: Generating {platform} pipeline... this may take 10-30 seconds.",
        )

        try:
            if platform == "jenkins":
                template_name, content = generate_jenkinsfile(description)
            else:
                template_name, content = generate_workflow(description)
        except Exception as e:
            logger.error("Generation failed: %s", e)
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f":x: Generation failed: {e}",
            )
            return

        # Post preview to channel (visible to all)
        blocks = pipeline_preview_blocks(platform, template_name, content, description)
        response = client.chat_postMessage(
            channel=channel_id,
            text=f"Generated {platform} pipeline for: {description}",
            blocks=blocks,
        )
        ts = response["ts"]

        # Store for approval handler
        _pending_generations[ts] = {
            "platform": platform,
            "content": content,
            "template_name": template_name,
            "request": description,
            "user_id": user_id,
            "channel_id": channel_id,
        }

    @app.action("copilot_approve")
    def handle_copilot_approve(ack, body, client: WebClient, logger=logger):
        ack()

        user_id = body["user"]["id"]
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]

        pending = _pending_generations.get(ts)
        if not pending:
            client.chat_postEphemeral(
                channel=channel,
                user=user_id,
                text=":x: Could not find the generation to approve — it may have expired.",
            )
            return

        platform = pending["platform"]
        content = pending["content"]
        request = pending["request"]

        # Update message to "Committing..."
        _update_message(client, channel, ts, body["message"]["blocks"], [
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": ":hourglass_flowing_sand: Committing to repository..."}],
            }
        ])

        settings = get_settings()
        repo = settings.github_default_repo

        try:
            file_path, commit_url = commit_pipeline_file(
                repo=repo,
                platform=platform,
                content=content,
                description=request,
            )
        except Exception as e:
            logger.error("Commit failed: %s", e)
            _update_message(client, channel, ts, body["message"]["blocks"], [
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f":x: Commit failed: {e}"}],
                }
            ])
            return

        committed_blocks = pipeline_committed_blocks(platform, file_path, commit_url, user_id)
        _update_message(client, channel, ts, body["message"]["blocks"], committed_blocks)
        del _pending_generations[ts]

    @app.action("copilot_cancel")
    def handle_copilot_cancel(ack, body, client: WebClient, logger=logger):
        ack()

        user_id = body["user"]["id"]
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]

        _pending_generations.pop(ts, None)
        _update_message(
            client, channel, ts,
            body["message"]["blocks"],
            pipeline_cancelled_blocks(user_id),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_message(
    client: WebClient,
    channel: str,
    ts: str,
    original_blocks: list[dict],
    replacement_tail: list[dict],
) -> None:
    """Replace actions + context blocks at the end with replacement_tail."""
    keep_types = {"header", "section", "divider"}
    trimmed = [b for b in original_blocks if b.get("type") in keep_types]
    updated = trimmed + replacement_tail
    try:
        client.chat_update(channel=channel, ts=ts, blocks=updated, text="Pipeline generation update")
    except Exception as e:
        logger.error("Failed to update copilot message %s: %s", ts, e)


def _post_help(client: WebClient, channel: str, user: str) -> None:
    client.chat_postEphemeral(
        channel=channel,
        user=user,
        text=(
            "*DevOps Copilot — Usage:*\n"
            "`/devops generate jenkins <description>` — Generate a Jenkinsfile\n"
            "`/devops generate github <description>` — Generate a GitHub Actions workflow\n"
            "`/devops generate jenkins list` — Show available Jenkins templates\n"
            "`/devops generate github list` — Show available GitHub Actions templates"
        ),
    )


def _post_template_list(client: WebClient, channel: str, user: str, platform: str) -> None:
    templates = list_templates(platform)
    if templates:
        template_list = "\n".join(f"• `{t}`" for t in templates)
        text = f"*Available {platform} templates:*\n{template_list}"
    else:
        text = f"No templates found for {platform}."
    client.chat_postEphemeral(channel=channel, user=user, text=text)
