"""
Unit tests for GitHub Actions Verification Crawler (Increment 13).
GitHub API calls are mocked — no live token required.
"""
import pytest
import respx
import httpx

from verification.actions_crawler import (
    verify_actions_config,
    _extract_secrets,
    _extract_runner_labels,
    _extract_action_refs,
)

SAMPLE_WORKFLOW = """\
name: CI Pipeline

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@main
        env:
          AWS_ACCESS_KEY: ${{ secrets.AWS_ACCESS_KEY }}
          AWS_SECRET_KEY: ${{ secrets.AWS_SECRET_KEY }}
      - name: Docker Build
        run: docker build .
        env:
          REGISTRY: ${{ secrets.ECR_REGISTRY }}

  deploy:
    runs-on: custom-runner-k8s
    needs: build
    steps:
      - uses: appleboy/ssh-action@v0.1.10
        with:
          password: ${{ secrets.DEPLOY_SSH_KEY }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
"""

GITHUB_REPO = "adil-khan-723/cicd-ai-copilot"
GITHUB_TOKEN = "ghp_testtoken"

SECRETS_API_RESPONSE = {
    "secrets": [
        {"name": "AWS_ACCESS_KEY"},
        {"name": "AWS_SECRET_KEY"},
        # ECR_REGISTRY and DEPLOY_SSH_KEY intentionally missing
    ],
    "total_count": 2,
}


class TestExtractSecrets:
    def test_extracts_all_secrets(self):
        secrets = _extract_secrets(SAMPLE_WORKFLOW)
        assert "AWS_ACCESS_KEY" in secrets
        assert "AWS_SECRET_KEY" in secrets
        assert "ECR_REGISTRY" in secrets
        assert "DEPLOY_SSH_KEY" in secrets

    def test_deduplicates(self):
        secrets = _extract_secrets(SAMPLE_WORKFLOW)
        assert secrets.count("DEPLOY_SSH_KEY") == 1

    def test_excludes_github_token(self):
        content = "token: ${{ secrets.GITHUB_TOKEN }}"
        assert "GITHUB_TOKEN" not in _extract_secrets(content)

    def test_no_secrets(self):
        assert _extract_secrets("run: echo hello") == []


class TestExtractRunnerLabels:
    def test_extracts_string_label(self):
        workflow = {"jobs": {"build": {"runs-on": "ubuntu-latest"}}}
        assert "ubuntu-latest" in _extract_runner_labels(workflow)

    def test_extracts_list_labels(self):
        workflow = {"jobs": {"build": {"runs-on": ["self-hosted", "linux"]}}}
        labels = _extract_runner_labels(workflow)
        assert "self-hosted" in labels
        assert "linux" in labels

    def test_custom_runner_label(self):
        import yaml
        workflow = yaml.safe_load(SAMPLE_WORKFLOW)
        labels = _extract_runner_labels(workflow)
        assert "ubuntu-latest" in labels
        assert "custom-runner-k8s" in labels


class TestExtractActionRefs:
    def test_extracts_uses(self):
        refs = _extract_action_refs(SAMPLE_WORKFLOW)
        assert "actions/checkout@v4" in refs
        assert "aws-actions/amazon-ecr-login@main" in refs

    def test_deduplicates(self):
        content = "uses: actions/checkout@v4\nuses: actions/checkout@v4\n"
        refs = _extract_action_refs(content)
        assert refs.count("actions/checkout@v4") == 1


class TestVerifyActionsConfig:
    @respx.mock
    def test_detects_missing_secrets(self):
        respx.get(f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets").mock(
            return_value=httpx.Response(200, json=SECRETS_API_RESPONSE)
        )

        report = verify_actions_config(
            SAMPLE_WORKFLOW, GITHUB_REPO, github_token=GITHUB_TOKEN
        )

        assert "ECR_REGISTRY" in report.missing_secrets
        assert "DEPLOY_SSH_KEY" in report.missing_secrets
        assert "AWS_ACCESS_KEY" not in report.missing_secrets
        assert "AWS_SECRET_KEY" not in report.missing_secrets

    def test_detects_unknown_runner(self):
        report = verify_actions_config(SAMPLE_WORKFLOW, GITHUB_REPO)
        assert "custom-runner-k8s" in report.missing_runners
        assert "ubuntu-latest" not in report.missing_runners

    def test_detects_unpinned_action(self):
        report = verify_actions_config(SAMPLE_WORKFLOW, GITHUB_REPO)
        assert "aws-actions/amazon-ecr-login@main" in report.unpinned_actions
        # @v4 and @v5 are version tags, not unpinned patterns we flag
        assert "actions/checkout@v4" not in report.unpinned_actions

    def test_no_token_skips_secrets(self):
        report = verify_actions_config(SAMPLE_WORKFLOW, GITHUB_REPO, github_token=None)
        assert not report.missing_secrets
        assert not report.errors

    def test_invalid_yaml(self):
        report = verify_actions_config(":: invalid: yaml: [[[", GITHUB_REPO)
        assert any("YAML" in e for e in report.errors)

    @respx.mock
    def test_api_403_skips_gracefully(self):
        respx.get(f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets").mock(
            return_value=httpx.Response(403, json={"message": "Forbidden"})
        )

        report = verify_actions_config(
            SAMPLE_WORKFLOW, GITHUB_REPO, github_token=GITHUB_TOKEN
        )
        # 403 → no missing secrets flagged, no errors
        assert not report.missing_secrets
        assert not report.errors

    def test_has_issues_with_missing_secrets(self):
        from verification.models import VerificationReport
        report = VerificationReport(platform="github")
        report.missing_secrets.append("MY_SECRET")
        assert report.has_issues

    def test_summary_lines_include_secrets_and_runners(self):
        from verification.models import VerificationReport
        report = VerificationReport(platform="github")
        report.missing_secrets.append("MY_SECRET")
        report.missing_runners.append("custom-k8s")
        report.unpinned_actions.append("actions/cache@main")
        lines = report.summary_lines()
        assert any("MY_SECRET" in l for l in lines)
        assert any("custom-k8s" in l for l in lines)
        assert any("actions/cache@main" in l for l in lines)
