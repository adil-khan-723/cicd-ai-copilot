"""Tests for enhanced Slack message templates (Increment 16)."""
from parser.models import FailureContext
from verification.models import VerificationReport, ToolMismatch
from slack.message_templates import failure_alert_blocks, analysis_complete_blocks


def make_context() -> FailureContext:
    return FailureContext(
        job_name="build-api",
        build_number=42,
        failed_stage="Docker Build",
        platform="jenkins",
        branch="main",
    )


def make_report() -> VerificationReport:
    report = VerificationReport(platform="jenkins")
    report.mismatched_tools.append(ToolMismatch("Maven3", "Maven-3", 0.91))
    report.missing_credentials.append("ECR_CREDENTIALS")
    return report


ANALYSIS_HIGH_CONF = {
    "root_cause": "pip dependency conflict with fastapi==99.0.0",
    "fix_suggestion": "Pin fastapi to a valid version in requirements.txt",
    "confidence": 0.88,
    "fix_type": "clear_cache",
}

ANALYSIS_LOW_CONF = {
    "root_cause": "Unclear — possibly transient",
    "fix_suggestion": "Manual review required.",
    "confidence": 0.45,
    "fix_type": "diagnostic_only",
}


class TestFailureAlertBlocks:
    def test_basic_blocks_present(self):
        blocks = failure_alert_blocks(make_context(), "ERROR: build failed")
        types = [b["type"] for b in blocks]
        assert "header" in types
        assert "section" in types
        assert "divider" in types

    def test_log_preview_included(self):
        blocks = failure_alert_blocks(make_context(), "fastapi==99.0.0 not found")
        text_blocks = [b for b in blocks if b.get("type") == "section"]
        all_text = " ".join(
            b.get("text", {}).get("text", "") for b in text_blocks
        )
        assert "fastapi==99.0.0" in all_text

    def test_log_truncated_at_300(self):
        long_log = "x" * 400
        blocks = failure_alert_blocks(make_context(), long_log)
        text_blocks = [b for b in blocks if b.get("type") == "section"]
        all_text = " ".join(b.get("text", {}).get("text", "") for b in text_blocks)
        assert "..." in all_text

    def test_verification_section_shown_when_issues(self):
        blocks = failure_alert_blocks(make_context(), "log", report=make_report())
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks if b.get("type") == "section"
        )
        assert "Verification Findings" in all_text
        assert "Maven3" in all_text
        assert "ECR_CREDENTIALS" in all_text

    def test_verification_section_hidden_when_no_issues(self):
        empty_report = VerificationReport(platform="jenkins")
        blocks = failure_alert_blocks(make_context(), "log", report=empty_report)
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks if b.get("type") == "section"
        )
        assert "Verification Findings" not in all_text

    def test_analysis_section_shown_when_provided(self):
        blocks = failure_alert_blocks(make_context(), "log", analysis=ANALYSIS_HIGH_CONF)
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks if b.get("type") == "section"
        )
        assert "AI Analysis" in all_text
        assert "88%" in all_text
        assert "pip dependency conflict" in all_text

    def test_analysis_pending_shown_when_no_analysis(self):
        blocks = failure_alert_blocks(make_context(), "log")
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        all_text = " ".join(
            e.get("text", "") for b in context_blocks for e in b.get("elements", [])
        )
        assert "Analysis pending" in all_text


class TestAnalysisCompleteBlocks:
    def _get_base_blocks(self) -> list[dict]:
        return failure_alert_blocks(make_context(), "log")

    def test_pending_context_replaced(self):
        base = self._get_base_blocks()
        updated = analysis_complete_blocks(base, ANALYSIS_HIGH_CONF)
        context_texts = [
            e.get("text", "")
            for b in updated if b.get("type") == "context"
            for e in b.get("elements", [])
        ]
        assert not any("Analysis pending" in t for t in context_texts)

    def test_high_confidence_adds_apply_button(self):
        base = self._get_base_blocks()
        updated = analysis_complete_blocks(base, ANALYSIS_HIGH_CONF, confidence_threshold=0.75)
        action_blocks = [b for b in updated if b.get("type") == "actions"]
        assert len(action_blocks) == 1
        button_ids = [e.get("action_id") for e in action_blocks[0].get("elements", [])]
        assert "apply_fix" in button_ids
        assert "dismiss_fix" in button_ids

    def test_low_confidence_shows_manual_review(self):
        base = self._get_base_blocks()
        updated = analysis_complete_blocks(base, ANALYSIS_LOW_CONF, confidence_threshold=0.75)
        action_blocks = [b for b in updated if b.get("type") == "actions"]
        assert len(action_blocks) == 1
        button_ids = [e.get("action_id") for e in action_blocks[0].get("elements", [])]
        assert "manual_review" in button_ids
        assert "apply_fix" not in button_ids

    def test_diagnostic_only_never_gets_apply_button(self):
        base = self._get_base_blocks()
        # Even with high confidence, diagnostic_only never gets Apply button
        analysis = {**ANALYSIS_HIGH_CONF, "fix_type": "diagnostic_only"}
        updated = analysis_complete_blocks(base, analysis, confidence_threshold=0.75)
        action_blocks = [b for b in updated if b.get("type") == "actions"]
        button_ids = [e.get("action_id") for e in action_blocks[0].get("elements", [])]
        assert "apply_fix" not in button_ids

    def test_analysis_text_in_updated_blocks(self):
        base = self._get_base_blocks()
        updated = analysis_complete_blocks(base, ANALYSIS_HIGH_CONF)
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in updated if b.get("type") == "section"
        )
        assert "pip dependency conflict" in all_text
        assert "88%" in all_text
