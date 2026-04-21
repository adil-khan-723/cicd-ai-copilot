"""
Phase 4 tests — Copilot mode: template selection, Jenkinsfile generator, configurator.
All LLM and external API calls are mocked.
"""
import pytest
from unittest.mock import patch, MagicMock

from copilot.template_selector import (
    select_jenkins_template,
    list_templates,
)
from copilot.pipeline_generator import generate_jenkinsfile, _is_valid_groovy, _extract_groovy
from copilot.jenkins_configurator import create_job, _xml_escape


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

    def test_list_templates_jenkins(self):
        templates = list_templates("jenkins")
        assert len(templates) >= 3
        assert any("generic" in t for t in templates)

    def test_list_templates_unknown_platform(self):
        assert list_templates("nonexistent") == []


# ---------------------------------------------------------------------------
# Groovy validation helpers
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
