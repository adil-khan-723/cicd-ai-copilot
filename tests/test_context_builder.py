"""Tests for Context Builder (Increment 14)."""
import pytest
from parser.models import FailureContext
from verification.models import VerificationReport, ToolMismatch
from analyzer.context_builder import build_context, count_tokens, TOTAL_BUDGET


def make_context(**kwargs) -> FailureContext:
    defaults = dict(
        job_name="build-api",
        build_number=42,
        failed_stage="Docker Build",
        platform="jenkins",
        branch="main",
    )
    defaults.update(kwargs)
    return FailureContext(**defaults)


def make_report_with_issues() -> VerificationReport:
    report = VerificationReport(platform="jenkins")
    report.mismatched_tools.append(ToolMismatch("Maven3", "Maven-3", 0.91))
    report.missing_credentials.append("ECR_CREDENTIALS")
    report.missing_plugins.append("docker-plugin")
    return report


class TestBuildContext:
    def test_includes_metadata(self):
        ctx = make_context()
        result = build_context("ERROR: build failed", None, ctx)
        assert "build-api" in result
        assert "Docker Build" in result
        assert "jenkins" in result

    def test_includes_branch_and_repo(self):
        ctx = make_context(repo="adil/cicd", branch="feature/auth")
        result = build_context("log", None, ctx)
        assert "feature/auth" in result
        assert "adil/cicd" in result

    def test_includes_verification_findings(self):
        ctx = make_context()
        report = make_report_with_issues()
        result = build_context("log", report, ctx)
        assert "Verification Findings" in result
        assert "Maven3" in result
        assert "ECR_CREDENTIALS" in result

    def test_skips_verification_when_no_issues(self):
        ctx = make_context()
        report = VerificationReport(platform="jenkins")  # no issues
        result = build_context("log", report, ctx)
        assert "Verification Findings" not in result

    def test_skips_verification_when_none(self):
        ctx = make_context()
        result = build_context("log", None, ctx)
        assert "Verification Findings" not in result

    def test_includes_log(self):
        ctx = make_context()
        result = build_context("fastapi==99.0.0 not found", None, ctx)
        assert "fastapi==99.0.0 not found" in result

    def test_total_tokens_within_budget(self):
        ctx = make_context()
        report = make_report_with_issues()
        # Generate a log that would exceed budget on its own
        big_log = "ERROR: something went wrong\n" * 200
        result = build_context(big_log, report, ctx)
        tokens = count_tokens(result)
        assert tokens <= TOTAL_BUDGET, f"Context used {tokens} tokens, budget is {TOTAL_BUDGET}"

    def test_truncated_log_contains_marker(self):
        ctx = make_context()
        big_log = "x " * 3000  # definitely over budget
        result = build_context(big_log, None, ctx)
        assert "[...truncated]" in result

    def test_short_log_not_truncated(self):
        ctx = make_context()
        short_log = "ERROR: pip install failed"
        result = build_context(short_log, None, ctx)
        assert "[...truncated]" not in result
        assert "ERROR: pip install failed" in result

    def test_token_count_stays_within_budget_with_all_fields(self):
        ctx = make_context(repo="adil-khan-723/cicd-ai-copilot", branch="feature/something-long")
        report = make_report_with_issues()
        # Add many issues
        for i in range(10):
            report.missing_credentials.append(f"CRED_{i}")
        big_log = "Step failed: " * 300
        result = build_context(big_log, report, ctx)
        tokens = count_tokens(result)
        assert tokens <= TOTAL_BUDGET, f"Context used {tokens} tokens"
