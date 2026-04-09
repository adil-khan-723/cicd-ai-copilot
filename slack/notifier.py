import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config import get_settings
from parser.models import FailureContext
from verification.models import VerificationReport
from slack.message_templates import failure_alert_blocks, analysis_complete_blocks

logger = logging.getLogger(__name__)


def get_slack_client() -> WebClient:
    return WebClient(token=get_settings().slack_bot_token)


def send_failure_alert(
    context: FailureContext,
    cleaned_log: str,
    report: VerificationReport | None = None,
    analysis: dict | None = None,
) -> str | None:
    """
    Post a formatted failure alert to the configured Slack channel.
    Returns the message timestamp (ts) for later updates, or None on failure.
    """
    settings = get_settings()
    client = get_slack_client()
    blocks = failure_alert_blocks(context, cleaned_log, report=report, analysis=analysis)

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


def update_with_analysis(
    ts: str,
    original_blocks: list[dict],
    analysis: dict,
) -> bool:
    """
    Update an existing Slack message (identified by ts) to replace 'Analysis pending...'
    with the full LLM analysis result + action buttons.

    Returns True on success, False on failure.
    """
    settings = get_settings()
    client = get_slack_client()
    updated_blocks = analysis_complete_blocks(original_blocks, analysis, settings.confidence_threshold)

    try:
        client.chat_update(
            channel=settings.slack_channel,
            ts=ts,
            blocks=updated_blocks,
            text=f"Analysis complete — {analysis.get('fix_type', 'diagnostic_only')}",
        )
        logger.info("Slack message %s updated with analysis", ts)
        return True
    except SlackApiError as e:
        logger.error("Failed to update Slack message: %s", e.response["error"])
        return False
