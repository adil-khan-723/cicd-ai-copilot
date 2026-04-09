"""
Slack Block Kit templates for Copilot mode (pipeline preview + approval flow).
"""

_PREVIEW_LINES = 20


def pipeline_preview_blocks(
    platform: str,
    template_name: str,
    content: str,
    request_summary: str,
) -> list[dict]:
    """
    Build a Block Kit message showing a generated pipeline preview with action buttons.

    Args:
        platform: 'jenkins' or 'github'
        template_name: e.g. 'jenkins/python-docker-ecr.groovy'
        content: Full generated pipeline content
        request_summary: Short description of what was requested
    """
    icon = ":jenkins:" if platform == "jenkins" else ":github:"
    lang = "groovy" if platform == "jenkins" else "yaml"
    file_type = "Jenkinsfile" if platform == "jenkins" else "workflow YAML"

    # Preview: first N lines
    lines = content.splitlines()
    preview_lines = lines[:_PREVIEW_LINES]
    preview = "\n".join(preview_lines)
    truncated = len(lines) > _PREVIEW_LINES

    preview_text = f"```{preview}```"
    if truncated:
        preview_text += f"\n_... ({len(lines) - _PREVIEW_LINES} more lines)_"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Generated {file_type}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{icon} *Request:* {request_summary}\n*Based on:* `{template_name}`",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":page_facing_up: *Preview* (first {_PREVIEW_LINES} lines)\n{preview_text}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve & Commit"},
                    "style": "primary",
                    "action_id": "copilot_approve",
                    "value": platform,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "style": "danger",
                    "action_id": "copilot_cancel",
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":information_source: Click *Approve & Commit* to push this file to your repo.",
                }
            ],
        },
    ]
    return blocks


def pipeline_committed_blocks(
    platform: str,
    file_path: str,
    commit_url: str,
    committed_by: str,
) -> list[dict]:
    """Message shown after successful commit."""
    file_type = "Jenkinsfile" if platform == "jenkins" else "workflow YAML"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: *{file_type} committed* by <@{committed_by}>\n"
                    f">  *File:* `{file_path}`\n"
                    f">  *Commit:* <{commit_url}|View on GitHub>"
                ),
            },
        }
    ]


def pipeline_cancelled_blocks(cancelled_by: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":no_entry_sign: Generation cancelled by <@{cancelled_by}>.",
            },
        }
    ]
