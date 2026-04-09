from parser.models import FailureContext


def failure_alert_blocks(context: FailureContext, cleaned_log: str) -> list[dict]:
    """Build Slack Block Kit payload for a pipeline failure alert."""

    platform_icon = ":github:" if context.platform == "github" else ":jenkins:"
    header = f":red_circle: Pipeline Failure: *{context.job_name}* #{context.build_number}"
    if context.repo:
        header += f"  |  {context.repo}"
    if context.branch:
        header += f"  (`{context.branch}`)"

    log_preview = cleaned_log[:300] + "..." if len(cleaned_log) > 300 else cleaned_log

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Pipeline Failure — {context.job_name}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": header},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Platform:* {platform_icon} {context.platform.capitalize()}"},
                {"type": "mrkdwn", "text": f"*Failed Stage:* `{context.failed_stage}`"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":mag: *Failed Stage Log*\n```{log_preview}```",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": ":hourglass_flowing_sand: Analysis pending..."}
            ],
        },
    ]
    return blocks
