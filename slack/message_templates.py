from parser.models import FailureContext
from verification.models import VerificationReport


def failure_alert_blocks(
    context: FailureContext,
    cleaned_log: str,
    report: VerificationReport | None = None,
    analysis: dict | None = None,
) -> list[dict]:
    """
    Build Slack Block Kit payload for a pipeline failure alert.

    Args:
        context: Parsed failure context (job, stage, platform, etc.)
        cleaned_log: Cleaned failed-stage log excerpt
        report: Optional verification report (tool mismatches, missing creds, etc.)
        analysis: Optional LLM analysis result (root_cause, fix_suggestion, confidence, fix_type)
    """
    platform_icon = ":github:" if context.platform == "github" else ":jenkins:"
    header = f":red_circle: Pipeline Failure: *{context.job_name}* #{context.build_number}"
    if context.repo:
        header += f"  |  {context.repo}"
    if context.branch:
        header += f"  (`{context.branch}`)"

    log_preview = cleaned_log[:300] + "..." if len(cleaned_log) > 300 else cleaned_log

    blocks: list[dict] = [
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
    ]

    # Verification findings section
    if report and report.has_issues:
        lines = report.summary_lines()
        findings_text = ":warning: *Tool Verification Findings*\n"
        findings_text += "\n".join(f">  :x: {line}" for line in lines)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": findings_text},
        })
        blocks.append({"type": "divider"})

    # Log preview section
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f":mag: *Failed Stage Log*\n```{log_preview}```",
        },
    })

    # Analysis section
    if analysis:
        confidence_pct = int(analysis.get("confidence", 0.0) * 100)
        fix_type = analysis.get("fix_type", "diagnostic_only")
        root_cause = analysis.get("root_cause", "Unknown")
        fix_suggestion = analysis.get("fix_suggestion", "Manual review required.")

        fix_icon = {
            "retry": ":repeat:",
            "clear_cache": ":wastebasket:",
            "pull_image": ":whale:",
            "increase_timeout": ":clock3:",
            "diagnostic_only": ":stethoscope:",
        }.get(fix_type, ":stethoscope:")

        analysis_text = (
            f":robot_face: *AI Analysis* ({confidence_pct}% confidence)\n"
            f">  *Root cause:* {root_cause}\n"
            f">  {fix_icon} *Suggested fix:* {fix_suggestion}"
        )
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": analysis_text},
        })
    else:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": ":hourglass_flowing_sand: Analysis pending..."}
            ],
        })

    return blocks


def analysis_complete_blocks(
    original_blocks: list[dict],
    analysis: dict,
    confidence_threshold: float = 0.75,
) -> list[dict]:
    """
    Replace the 'Analysis pending...' context block with the full analysis result.
    Used when updating an existing Slack message after LLM analysis completes.
    """
    # Remove the last "Analysis pending..." context block if present
    blocks = [
        b for b in original_blocks
        if not (
            b.get("type") == "context"
            and any("Analysis pending" in e.get("text", "") for e in b.get("elements", []))
        )
    ]

    confidence_pct = int(analysis.get("confidence", 0.0) * 100)
    fix_type = analysis.get("fix_type", "diagnostic_only")
    root_cause = analysis.get("root_cause", "Unknown")
    fix_suggestion = analysis.get("fix_suggestion", "Manual review required.")

    fix_icon = {
        "retry": ":repeat:",
        "clear_cache": ":wastebasket:",
        "pull_image": ":whale:",
        "increase_timeout": ":clock3:",
        "diagnostic_only": ":stethoscope:",
    }.get(fix_type, ":stethoscope:")

    analysis_text = (
        f":robot_face: *AI Analysis* ({confidence_pct}% confidence)\n"
        f">  *Root cause:* {root_cause}\n"
        f">  {fix_icon} *Suggested fix:* {fix_suggestion}"
    )

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": analysis_text},
    })

    # Add action buttons if confidence meets threshold and fix is actionable
    if analysis.get("confidence", 0.0) >= confidence_threshold and fix_type != "diagnostic_only":
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"Apply Fix ({fix_type.replace('_', ' ').title()})"},
                    "style": "primary",
                    "action_id": "apply_fix",
                    "value": fix_type,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Dismiss"},
                    "action_id": "dismiss_fix",
                },
            ],
        })
    else:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Manual Review"},
                    "action_id": "manual_review",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Dismiss"},
                    "action_id": "dismiss_fix",
                },
            ],
        })

    return blocks
