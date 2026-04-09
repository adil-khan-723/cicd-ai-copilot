"""
Phase 4 tests — Copilot mode: template selection, generators, committer, configurator.
All LLM and external API calls are mocked.
"""
import pytest
from unittest.mock import patch, MagicMock

from copilot.template_selector import (
    select_jenkins_template,
    select_github_template,
    list_templates,
)
from copilot.pipeline_generator import generate_jenkinsfile, _is_valid_groovy, _extract_groovy
from copilot.actions_generator import generate_workflow, _is_valid_yaml, _extract_yaml
from copilot.repo_committer import _determine_file_path, _slugify, commit_pipeline_file
from copilot.jenkins_configurator import create_job, _xml_escape
from slack.copilot_message_templates import (
    pipeline_preview_blocks,
    pipeline_committed_blocks,
    pipeline_cancelled_blocks,
)


# ---------------------------------------------------------------------------
# Template selector tests
# ---------------------------------------------------------------------------

class TestTemplateSelector:
    def test_python_ecr_selects_python_docker_ecr(self):
        name, content = select_jenkins_template("python app docker build push to ecr")
        assert "python-docker-ecr" in name
        assert "pipeline" in content.lower()

    def test_node_docker_selects_node_template(self):
        name, content = select_jenkins_template("node.js docker build push")
        assert "node-docker" in name

    def test_unknown_falls_back_to_generic(self):
        name, content = select_jenkins_template("deploy my rust application to k8s")
        assert "generic" in name

    def test_github_python_selects_python_ci(self):
        name, content = select_github_template("python app run test lint")
        assert "python-ci" in name

    def test_github_docker_ecr_selects_docker_ecr(self):
        name, content = select_github_template("docker build push to ecr")
        assert "docker-ecr" in name

    def test_github_unknown_falls_back_to_generic(self):
        name, content = select_github_template("rust wasm build")
        assert "generic" in name

    def test_list_templates_jenkins(self):
        templates = list_templates("jenkins")
        assert len(templates) >= 3
        assert any("generic" in t for t in templates)

    def test_list_templates_github(self):
        templates = list_templates("github")
        assert len(templates) >= 3

    def test_list_templates_unknown_platform(self):
        assert list_templates("nonexistent") == []


# ---------------------------------------------------------------------------
# Groovy / YAML validation helpers
# ---------------------------------------------------------------------------

class TestValidationHelpers:
    def test_valid_groovy(self):
        content = "pipeline {\n  agent any\n  stages {\n    stage('Build') { steps { sh 'make' } }\n  }\n}"
        assert _is_valid_groovy(content) is True

    def test_invalid_groovy_unbalanced_braces(self):
        content = "pipeline {\n  agent any\n  stages {\n"
        assert _is_valid_groovy(content) is False

    def test_invalid_groovy_missing_stages(self):
        content = "pipeline {\n  agent any\n}"
        assert _is_valid_groovy(content) is False

    def test_extract_groovy_strips_fence(self):
        raw = "```groovy\npipeline { agent any\n  stages { stage('X') { steps { sh 'a' } } }\n}\n```"
        result = _extract_groovy(raw)
        assert result.startswith("pipeline")

    def test_valid_yaml(self):
        content = "name: CI\non:\n  push:\n    branches: [main]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
        assert _is_valid_yaml(content) is True

    def test_invalid_yaml_missing_jobs(self):
        content = "name: CI\non:\n  push:\n    branches: [main]\n"
        assert _is_valid_yaml(content) is False

    def test_invalid_yaml_syntax_error(self):
        assert _is_valid_yaml(":: bad: [yaml") is False

    def test_extract_yaml_strips_fence(self):
        raw = "```yaml\nname: CI\non:\n  push:\njobs:\n  build:\n    runs-on: ubuntu-latest\n```"
        result = _extract_yaml(raw)
        assert result.startswith("name:")


# ---------------------------------------------------------------------------
# Generator tests (LLM mocked)
# ---------------------------------------------------------------------------

VALID_JENKINSFILE = """\
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sh 'make build'
            }
        }
    }
}"""

VALID_WORKFLOW = """\
name: CI
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


class TestJenkinsGenerator:
    def test_returns_valid_jenkinsfile(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = VALID_JENKINSFILE

        with patch("copilot.pipeline_generator.get_provider", return_value=mock_provider):
            template_name, content = generate_jenkinsfile("python docker ecr build")

        assert content.strip().startswith("pipeline")
        assert _is_valid_groovy(content)
        assert mock_provider.complete.call_count == 1

    def test_retries_on_invalid_output(self):
        mock_provider = MagicMock()
        # First call returns garbage, second call returns valid
        mock_provider.complete.side_effect = ["not valid groovy at all", VALID_JENKINSFILE]

        with patch("copilot.pipeline_generator.get_provider", return_value=mock_provider):
            template_name, content = generate_jenkinsfile("build my app")

        assert mock_provider.complete.call_count == 2
        assert _is_valid_groovy(content)

    def test_template_name_returned(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = VALID_JENKINSFILE

        with patch("copilot.pipeline_generator.get_provider", return_value=mock_provider):
            template_name, _ = generate_jenkinsfile("python docker ecr")

        assert "jenkins" in template_name


class TestActionsGenerator:
    def test_returns_valid_yaml(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = VALID_WORKFLOW

        with patch("copilot.actions_generator.get_provider", return_value=mock_provider):
            template_name, content = generate_workflow("python tests lint")

        assert _is_valid_yaml(content)
        assert mock_provider.complete.call_count == 1

    def test_retries_on_invalid_yaml(self):
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = [":: invalid yaml [[[", VALID_WORKFLOW]

        with patch("copilot.actions_generator.get_provider", return_value=mock_provider):
            template_name, content = generate_workflow("deploy app")

        assert mock_provider.complete.call_count == 2
        assert _is_valid_yaml(content)


# ---------------------------------------------------------------------------
# Repo committer tests
# ---------------------------------------------------------------------------

class TestRepoCommitter:
    def test_jenkinsfile_path(self):
        assert _determine_file_path("jenkins", "anything") == "Jenkinsfile"

    def test_github_actions_path(self):
        path = _determine_file_path("github", "Python CI with Docker")
        assert path.startswith(".github/workflows/")
        assert path.endswith(".yml")

    def test_slugify_basic(self):
        assert _slugify("Python Docker ECR build") == "python-docker-ecr-build"

    def test_slugify_special_chars(self):
        assert _slugify("my app!!! build") == "my-app-build"

    def test_slugify_empty(self):
        assert _slugify("") == "pipeline"

    def test_commit_creates_file(self):
        from github import GithubException
        mock_repo = MagicMock()
        not_found = GithubException(404, {"message": "Not Found"}, None)
        mock_repo.get_contents.side_effect = not_found
        mock_commit = MagicMock()
        mock_commit.html_url = "https://github.com/test/repo/commit/abc"
        mock_repo.create_file.return_value = {"commit": mock_commit}

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        with patch("copilot.repo_committer.Github", return_value=mock_gh):
            with patch("copilot.repo_committer.get_settings") as mock_settings:
                mock_settings.return_value.github_token = "ghp_test"
                file_path, commit_url = commit_pipeline_file(
                    repo="adil/test",
                    platform="jenkins",
                    content="pipeline {}",
                    description="test pipeline",
                )

        assert file_path == "Jenkinsfile"
        assert "github.com" in commit_url

    def test_no_token_raises(self):
        with patch("copilot.repo_committer.get_settings") as mock_settings:
            mock_settings.return_value.github_token = ""
            with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
                commit_pipeline_file("adil/test", "jenkins", "content", "desc")


# ---------------------------------------------------------------------------
# Jenkins configurator tests
# ---------------------------------------------------------------------------

class TestJenkinsConfigurator:
    def test_xml_escape(self):
        assert _xml_escape("<hello & world>") == "&lt;hello &amp; world&gt;"

    def test_creates_new_job(self):
        mock_server = MagicMock()
        mock_server.job_exists.return_value = False

        with patch("copilot.jenkins_configurator.jenkins.Jenkins", return_value=mock_server):
            with patch("copilot.jenkins_configurator.get_settings") as mock_settings:
                mock_settings.return_value.jenkins_url = "http://jenkins:8080"
                mock_settings.return_value.jenkins_user = "admin"
                mock_settings.return_value.jenkins_token = "token"
                url = create_job("my-pipeline", VALID_JENKINSFILE)

        mock_server.create_job.assert_called_once()
        assert "my-pipeline" in url

    def test_updates_existing_job(self):
        mock_server = MagicMock()
        mock_server.job_exists.return_value = True

        with patch("copilot.jenkins_configurator.jenkins.Jenkins", return_value=mock_server):
            with patch("copilot.jenkins_configurator.get_settings") as mock_settings:
                mock_settings.return_value.jenkins_url = "http://jenkins:8080"
                mock_settings.return_value.jenkins_user = "admin"
                mock_settings.return_value.jenkins_token = "token"
                url = create_job("my-pipeline", VALID_JENKINSFILE)

        mock_server.reconfig_job.assert_called_once()
        mock_server.create_job.assert_not_called()

    def test_no_token_raises(self):
        with patch("copilot.jenkins_configurator.get_settings") as mock_settings:
            mock_settings.return_value.jenkins_url = "http://localhost:8080"
            mock_settings.return_value.jenkins_token = ""
            with pytest.raises(RuntimeError, match="not configured"):
                create_job("test", "pipeline {}")


# ---------------------------------------------------------------------------
# Copilot Slack message template tests
# ---------------------------------------------------------------------------

class TestCopilotMessageTemplates:
    def test_preview_blocks_structure(self):
        blocks = pipeline_preview_blocks(
            "jenkins", "jenkins/generic.groovy",
            VALID_JENKINSFILE, "python docker ecr"
        )
        types = [b["type"] for b in blocks]
        assert "header" in types
        assert "actions" in types

    def test_preview_blocks_has_approve_and_cancel(self):
        blocks = pipeline_preview_blocks("jenkins", "t", "content", "req")
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 1
        action_ids = [e["action_id"] for e in action_blocks[0]["elements"]]
        assert "copilot_approve" in action_ids
        assert "copilot_cancel" in action_ids

    def test_committed_blocks_contains_file_path(self):
        blocks = pipeline_committed_blocks("jenkins", "Jenkinsfile", "http://github.com/c/1", "U123")
        all_text = " ".join(b.get("text", {}).get("text", "") for b in blocks)
        assert "Jenkinsfile" in all_text
        assert "U123" in all_text

    def test_cancelled_blocks_mentions_user(self):
        blocks = pipeline_cancelled_blocks("U456")
        all_text = " ".join(b.get("text", {}).get("text", "") for b in blocks)
        assert "U456" in all_text

    def test_long_content_truncated_in_preview(self):
        long_content = "\n".join(f"line {i}" for i in range(50))
        blocks = pipeline_preview_blocks("github", "t", long_content, "req")
        all_text = " ".join(b.get("text", {}).get("text", "") for b in blocks if b["type"] == "section")
        # Should mention truncation
        assert "more lines" in all_text
