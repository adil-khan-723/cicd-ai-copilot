"""
Slack Bolt approval handler (Increment 17).

Handles button clicks from failure alert messages:
  - apply_fix    → execute fix, update message with result
  - dismiss_fix  → update message to dismissed
  - manual_review → update message to manual review note

Fix execution is delegated to agent.fix_executor.
All executions are recorded in the audit log.
"""
import json
import logging
from slack_bolt import App
from slack_sdk import WebClient

from config import get_settings
from agent.fix_executor import execute_fix
from agent.audit_log import log_fix
from slack.message_templates import analysis_complete_blocks

logger = logging.getLogger(__name__)


def register_approval_handlers(app: App) -> None:
    """Register all action handlers on the given Slack Bolt app."""

    @app.action("apply_fix")
    def handle_apply_fix(ack, body, client: WebClient, logger=logger):
        ack()

        user_id = body["user"]["id"]
        fix_type = body["actions"][0].get("value", "retry")
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        message = body["message"]

        # Extract job context from the message metadata (stored in blocks or text)
        job_name, build_number = _extract_job_context(message)

        logger.info("Fix approved: %s by %s for %s #%s", fix_type, user_id, job_name, build_number)

        # Update message to "Processing..."
        _update_message_processing(client, channel, ts, message["blocks"], fix_type)

        # Execute the fix
        result = execute_fix(fix_type, job_name=job_name, build_number=build_number)

        # Log to audit trail
        log_fix(
            fix_type=fix_type,
            triggered_by=user_id,
            job_name=job_name,
            build_number=build_number,
            result="success" if result.success else "failed",
            confidence_at_trigger=_extract_confidence(message),
        )

        # Update message with outcome
        _update_message_result(client, channel, ts, message["blocks"], fix_type, result)

    @app.action("dismiss_fix")
    def handle_dismiss_fix(ack, body, client: WebClient, logger=logger):
        ack()

        user_id = body["user"]["id"]
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        message = body["message"]
        job_name, build_number = _extract_job_context(message)

        logger.info("Fix dismissed by %s for %s #%s", user_id, job_name, build_number)

        log_fix(
            fix_type="dismissed",
            triggered_by=user_id,
            job_name=job_name,
            build_number=build_number,
            result="dismissed",
            confidence_at_trigger=_extract_confidence(message),
        )

        _update_message_dismissed(client, channel, ts, message["blocks"], user_id)

    @app.action("manual_review")
    def handle_manual_review(ack, body, client: WebClient, logger=logger):
        ack()

        user_id = body["user"]["id"]
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        message = body["message"]
        job_name, build_number = _extract_job_context(message)

        logger.info("Manual review acknowledged by %s for %s #%s", user_id, job_name, build_number)

        log_fix(
            fix_type="manual_review",
            triggered_by=user_id,
            job_name=job_name,
            build_number=build_number,
            result="acknowledged",
            confidence_at_trigger=_extract_confidence(message),
        )

        _update_message_manual_review(client, channel, ts, message["blocks"], user_id)


# ---------------------------------------------------------------------------
# Message update helpers
# ---------------------------------------------------------------------------

def _update_message_processing(
    client: WebClient, channel: str, ts: str, blocks: list[dict], fix_type: str
) -> None:
    updated = _replace_actions(blocks, [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f":hourglass_flowing_sand: Applying fix: *{fix_type.replace('_', ' ')}*..."}],
    }])
    _try_update(client, channel, ts, updated, f"Applying fix: {fix_type}")


def _update_message_result(
    client: WebClient, channel: str, ts: str, blocks: list[dict], fix_type: str, result
) -> None:
    if result.success:
        icon = ":white_check_mark:"
        detail = result.detail or "Fix applied successfully."
    else:
        icon = ":x:"
        detail = result.detail or "Fix failed — manual intervention required."

    updated = _replace_actions(blocks, [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"{icon} *{fix_type.replace('_', ' ').title()}*: {detail}"}],
    }])
    _try_update(client, channel, ts, updated, f"Fix result: {fix_type}")


def _update_message_dismissed(
    client: WebClient, channel: str, ts: str, blocks: list[dict], user_id: str
) -> None:
    updated = _replace_actions(blocks, [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f":no_entry_sign: Dismissed by <@{user_id}>"}],
    }])
    _try_update(client, channel, ts, updated, "Fix dismissed")


def _update_message_manual_review(
    client: WebClient, channel: str, ts: str, blocks: list[dict], user_id: str
) -> None:
    updated = _replace_actions(blocks, [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f":eyes: Manual review acknowledged by <@{user_id}>"}],
    }])
    _try_update(client, channel, ts, updated, "Manual review acknowledged")


def _replace_actions(blocks: list[dict], replacement: list[dict]) -> list[dict]:
    """Strip all actions blocks and append replacement blocks."""
    return [b for b in blocks if b.get("type") != "actions"] + replacement


def _try_update(client: WebClient, channel: str, ts: str, blocks: list[dict], text: str) -> None:
    try:
        client.chat_update(channel=channel, ts=ts, blocks=blocks, text=text)
    except Exception as e:
        logger.error("Failed to update Slack message %s: %s", ts, e)


# ---------------------------------------------------------------------------
# Context extraction from message
# ---------------------------------------------------------------------------

def _extract_job_context(message: dict) -> tuple[str, str]:
    """Extract job_name and build_number from the Slack message text or header block."""
    # The header block text is: "Pipeline Failure — {job_name}"
    for block in message.get("blocks", []):
        if block.get("type") == "header":
            text = block.get("text", {}).get("text", "")
            if "Pipeline Failure — " in text:
                job_name = text.replace("Pipeline Failure — ", "").strip()
                break
    else:
        job_name = "unknown-job"

    # Build number is in the message text: "... #{build_number} — ..."
    import re
    text = message.get("text", "")
    match = re.search(r"#(\d+)", text)
    build_number = match.group(1) if match else "0"

    return job_name, build_number


def _extract_confidence(message: dict) -> float:
    """Extract confidence from analysis section text, e.g. '(88% confidence)'."""
    import re
    for block in message.get("blocks", []):
        if block.get("type") == "section":
            text = block.get("text", {}).get("text", "")
            match = re.search(r"\((\d+)%\s*confidence\)", text)
            if match:
                return int(match.group(1)) / 100.0
    return 0.0
