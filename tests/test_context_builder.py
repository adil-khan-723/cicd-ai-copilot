"""Tests for Context Builder."""
import pytest
from parser.models import FailureContext
from verification.models import VerificationReport, ToolMismatch
from analyzer.context_builder import build_context, count_tokens, TOTAL_BUDGET, _extract_stage_block


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
        for i in range(10):
            report.missing_credentials.append(f"CRED_{i}")
        big_log = "Step failed: " * 300
        result = build_context(big_log, report, ctx)
        tokens = count_tokens(result)
        assert tokens <= TOTAL_BUDGET, f"Context used {tokens} tokens"


SAMPLE_JENKINSFILE = """
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sh 'mvn package'
                echo 'Build done'
            }
        }
        stage('Test') {
            steps {
                sh 'mvn test'
            }
        }
        stage('Deploy') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'docker-hub-creds')]) {
                    sh 'docker push myapp'
                }
            }
        }
    }
}
"""

TYPO_JENKINSFILE = """
pipeline {
    agent any
    stages {
        stage('Hello') {
            steps {
                echo1 'Hello World'
            }
        }
    }
}
"""


class TestExtractStageBlock:
    def test_extracts_exact_stage(self):
        block = _extract_stage_block(SAMPLE_JENKINSFILE, "Build")
        assert "stage('Build')" in block
        assert "mvn package" in block
        assert "mvn test" not in block  # shouldn't bleed into Test stage

    def test_extracts_nested_stage(self):
        block = _extract_stage_block(SAMPLE_JENKINSFILE, "Deploy")
        assert "withCredentials" in block
        assert "docker push" in block

    def test_returns_empty_when_stage_not_found(self):
        block = _extract_stage_block(SAMPLE_JENKINSFILE, "Nonexistent")
        assert block == ""

    def test_returns_empty_when_jenkinsfile_empty(self):
        assert _extract_stage_block("", "Build") == ""

    def test_case_insensitive_match(self):
        block = _extract_stage_block(SAMPLE_JENKINSFILE, "build")
        assert "mvn package" in block

    def test_typo_stage_extracted(self):
        block = _extract_stage_block(TYPO_JENKINSFILE, "Hello")
        assert "echo1" in block


class TestBuildContextWithStageSnippet:
    def test_includes_stage_snippet_when_jenkinsfile_provided(self):
        ctx = make_context(failed_stage="Build")
        result = build_context("log", None, ctx, jenkinsfile=SAMPLE_JENKINSFILE)
        assert "Failing Stage Source" in result
        assert "mvn package" in result

    def test_excludes_other_stages(self):
        ctx = make_context(failed_stage="Build")
        result = build_context("log", None, ctx, jenkinsfile=SAMPLE_JENKINSFILE)
        assert "mvn test" not in result

    def test_no_snippet_when_no_jenkinsfile(self):
        ctx = make_context(failed_stage="Build")
        result = build_context("log", None, ctx)
        assert "Failing Stage Source" not in result

    def test_no_snippet_when_stage_not_found(self):
        ctx = make_context(failed_stage="Nonexistent")
        result = build_context("log", None, ctx, jenkinsfile=SAMPLE_JENKINSFILE)
        assert "Failing Stage Source" not in result

    def test_typo_step_visible_to_llm(self):
        ctx = make_context(failed_stage="Hello")
        result = build_context("ERROR: No such DSL method", None, ctx, jenkinsfile=TYPO_JENKINSFILE)
        assert "echo1" in result

    def test_token_budget_respected_with_snippet(self):
        ctx = make_context(failed_stage="Build", repo="org/repo", branch="main")
        report = make_report_with_issues()
        big_log = "ERROR line\n" * 300
        result = build_context(big_log, report, ctx, jenkinsfile=SAMPLE_JENKINSFILE)
        tokens = count_tokens(result)
        assert tokens <= TOTAL_BUDGET, f"Context used {tokens} tokens, budget is {TOTAL_BUDGET}"
