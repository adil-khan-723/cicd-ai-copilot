"""
Phase 1 integration test — full flow without LLM:
  Webhook payload → parse → extract logs → clean → Slack alert
"""
import pytest
from unittest.mock import patch, MagicMock
from parser.pipeline_parser import parse_failure
from parser.log_extractor import extract_failed_logs
from parser.log_cleaner import clean_log
from slack.notifier import send_failure_alert


JENKINS_PAYLOAD = {
    "job_name": "build-api",
    "build_number": 42,
    "result": "FAILURE",
    "branch": "main",
    "log": (
        "[Pipeline] stage (Checkout)\n"
        "[INFO] Cloning repository\n"
        "[Pipeline] stage (Docker Build)\n"
        "[INFO] \x1b[32mStarting docker build\x1b[0m\n"
        "14:23:11 Step 1/8 : FROM python:3.11\n"
        "[INFO] Step 2/8 : RUN pip install -r requirements.txt\n"
        "14:23:45 ERROR: Could not find a version that satisfies the requirement fastapi==99.0.0\n"
        "14:23:45 ERROR: No matching distribution found for fastapi==99.0.0\n"
        "##################################\n"
        "[Pipeline] stage (Test)\n"
        "[INFO] Skipped\n"
    ),
}

GITHUB_PAYLOAD = {
    "workflow_run": {
        "name": "CI Pipeline",
        "run_number": 17,
        "head_branch": "feature/auth",
        "repository": {"full_name": "adil-khan-723/cicd-ai-copilot"},
    },
    "failed_job": "build / Docker Build",
    "log": (
        "##[group]Run docker build\n"
        "Starting docker build...\n"
        "Step 1/5: FROM node:18\n"
        "ERROR: failed to solve: node:18: not found\n"
        "##[endgroup]\n"
    ),
}


class TestPipelineParser:
    def test_jenkins_parse(self):
        ctx = parse_failure(JENKINS_PAYLOAD, source="jenkins")
        assert ctx.job_name == "build-api"
        assert ctx.build_number == 42
        assert ctx.platform == "jenkins"
        assert ctx.failed_stage == "Docker Build"

    def test_github_parse(self):
        ctx = parse_failure(GITHUB_PAYLOAD, source="github")
        assert ctx.job_name == "CI Pipeline"
        assert ctx.build_number == 17
        assert ctx.platform == "github"
        assert "Docker Build" in ctx.failed_stage

    def test_unknown_source_falls_back(self):
        ctx = parse_failure(JENKINS_PAYLOAD)
        assert ctx.job_name == "build-api"


class TestLogExtractor:
    def test_extracts_jenkins_stage(self):
        ctx = parse_failure(JENKINS_PAYLOAD, source="jenkins")
        extracted = extract_failed_logs(ctx)
        assert "fastapi==99.0.0" in extracted
        # Passing stage logs must NOT be present
        assert "Cloning repository" not in extracted

    def test_extracts_github_step(self):
        ctx = parse_failure(GITHUB_PAYLOAD, source="github")
        extracted = extract_failed_logs(ctx)
        assert "failed to solve" in extracted

    def test_respects_max_chars(self):
        big_log = "x" * 5000
        ctx = parse_failure({**JENKINS_PAYLOAD, "log": big_log}, source="jenkins")
        extracted = extract_failed_logs(ctx)
        assert len(extracted) <= 2100  # 2000 + "[...truncated]\n" prefix


class TestLogCleaner:
    def test_strips_ansi(self):
        raw = "\x1b[32mSuccess\x1b[0m"
        assert clean_log(raw) == "Success"

    def test_strips_timestamps(self):
        raw = "14:23:45 ERROR: something failed"
        assert "14:23:45" not in clean_log(raw)
        assert "ERROR: something failed" in clean_log(raw)

    def test_strips_info_prefix(self):
        raw = "[INFO] Starting build\n[Pipeline] Running step"
        cleaned = clean_log(raw)
        assert "[INFO]" not in cleaned
        assert "[Pipeline]" not in cleaned

    def test_collapses_blank_lines(self):
        raw = "line1\n\n\n\n\nline2"
        assert "\n\n\n" not in clean_log(raw)

    def test_full_jenkins_log(self):
        ctx = parse_failure(JENKINS_PAYLOAD, source="jenkins")
        extracted = extract_failed_logs(ctx)
        cleaned = clean_log(extracted)
        assert "fastapi==99.0.0" in cleaned
        assert "\x1b[" not in cleaned
        assert "[INFO]" not in cleaned


class TestSlackNotifier:
    def test_sends_alert(self):
        ctx = parse_failure(JENKINS_PAYLOAD, source="jenkins")
        extracted = extract_failed_logs(ctx)
        cleaned = clean_log(extracted)

        mock_response = MagicMock()
        mock_response.__getitem__ = lambda self, key: "1234567890.123456" if key == "ts" else None

        with patch("slack.notifier.get_slack_client") as mock_client_factory:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = mock_response
            mock_client_factory.return_value = mock_client

            ts = send_failure_alert(ctx, cleaned)

            mock_client.chat_postMessage.assert_called_once()
            call_kwargs = mock_client.chat_postMessage.call_args.kwargs
            assert call_kwargs["channel"] == "#devops-alerts"
            assert "build-api" in call_kwargs["text"]
            assert len(call_kwargs["blocks"]) > 0
