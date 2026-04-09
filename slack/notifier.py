import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config import get_settings
from parser.models import FailureContext
from slack.message_templates import failure_alert_blocks

logger = logging.getLogger(__name__)


def get_slack_client() -> WebClient:
    return WebClient(token=get_settings().slack_bot_token)


def send_failure_alert(context: FailureContext, cleaned_log: str) -> str | None:
    """
    Post a formatted failure alert to the configured Slack channel.
    Returns the message timestamp (ts) for later updates, or None on failure.
    """
    settings = get_settings()
    client = get_slack_client()
    blocks = failure_alert_blocks(context, cleaned_log)

    try:
        response = client.chat_postMessage(
            channel=settings.slack_channel,
            text=f"Pipeline failure: {context.job_name} #{context.build_number} — {context.failed_stage}",
            blocks=blocks,
        )
        ts = response["ts"]
        logger.info("Slack alert sent: %s", ts)
        return ts
    except SlackApiError as e:
        logger.error("Failed to send Slack alert: %s", e.response["error"])
        return None
