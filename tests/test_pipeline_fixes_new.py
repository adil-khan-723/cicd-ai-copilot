"""Tests for configure_tool and configure_credential fix functions."""
import pytest
from unittest.mock import MagicMock, patch
import jenkins as jenkins_lib
from agent.pipeline_fixes import configure_tool, configure_credential


class TestConfigureTool:
    def test_patches_tool_name_in_jenkinsfile(self):
        """Replaces the wrong tool name with the correct one and reconfigures the job."""
        config_xml = """<project>
  <definition>
    <script>pipeline {
  tools { maven 'Maven3' }
  stages { stage('Build') { steps { sh 'mvn package' } } }
}</script>
  </definition>
</project>"""
        server = MagicMock()
        server.get_job_config.return_value = config_xml
        server.reconfig_job.return_value = None

        with patch("agent.pipeline_fixes._get_jenkins_server", return_value=server):
            result = configure_tool(
                job_name="java-pipeline",
                build_number="5",
                referenced_name="Maven3",
                configured_name="Maven-3",
            )

        assert result.success is True
        assert result.fix_type == "configure_tool"
        assert "Maven-3" in result.detail

        # Verify reconfig_job was called with patched XML
        called_xml = server.reconfig_job.call_args[0][1]
        assert "Maven-3" in called_xml
        assert "Maven3'" not in called_xml  # old name gone (with quote after it)

    def test_returns_failure_when_tool_not_found_in_xml(self):
        """Returns failure FixResult if the referenced name is not in config XML."""
        config_xml = "<project><definition><script>pipeline {}</script></definition></project>"
        server = MagicMock()
        server.get_job_config.return_value = config_xml

        with patch("agent.pipeline_fixes._get_jenkins_server", return_value=server):
            result = configure_tool(
                job_name="java-pipeline",
                build_number="5",
                referenced_name="Maven3",
                configured_name="Maven-3",
            )

        assert result.success is False
        assert "not found" in result.detail.lower()

    def test_returns_failure_on_jenkins_exception(self):
        server = MagicMock()
        server.get_job_config.side_effect = jenkins_lib.JenkinsException("HTTP 404")

        with patch("agent.pipeline_fixes._get_jenkins_server", return_value=server):
            result = configure_tool("java-pipeline", "5", "Maven3", "Maven-3")

        assert result.success is False
        assert result.fix_type == "configure_tool"


class TestConfigureCredential:
    def test_creates_credential_in_jenkins(self):
        """Creates a username/password credential placeholder in Jenkins."""
        server = MagicMock()

        crumb_response = MagicMock()
        crumb_response.raise_for_status.return_value = None
        crumb_response.json.return_value = {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc123"}

        create_response = MagicMock()
        create_response.status_code = 200

        with (
            patch("agent.pipeline_fixes._get_jenkins_server", return_value=server),
            patch("requests.get", return_value=crumb_response),
            patch("requests.post", return_value=create_response),
        ):
            result = configure_credential(
                job_name="node-deploy",
                build_number="3",
                credential_id="ECR_CREDENTIALS",
            )

        assert result.success is True
        assert result.fix_type == "configure_credential"
        assert "ECR_CREDENTIALS" in result.detail

    def test_returns_failure_on_jenkins_exception(self):
        server = MagicMock()
        server.create_credential.side_effect = jenkins_lib.JenkinsException("403 Forbidden")

        with patch("agent.pipeline_fixes._get_jenkins_server", return_value=server):
            result = configure_credential("node-deploy", "3", "ECR_CREDENTIALS")

        assert result.success is False
        assert result.fix_type == "configure_credential"

    def test_injects_secret_text_value(self):
        server = MagicMock()
        crumb_response = MagicMock()
        crumb_response.raise_for_status.return_value = None
        crumb_response.json.return_value = {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc123"}
        create_response = MagicMock()
        create_response.status_code = 200
        posted_xml = {}

        def capture_post(url, data, **kwargs):
            posted_xml["body"] = data.decode("utf-8")
            return create_response

        with (
            patch("agent.pipeline_fixes._get_jenkins_server", return_value=server),
            patch("requests.get", return_value=crumb_response),
            patch("requests.post", side_effect=capture_post),
        ):
            result = configure_credential(
                job_name="node-deploy",
                build_number="3",
                credential_id="MY_TOKEN",
                credential_type="secret_text",
                secret_value="supersecret",
            )

        assert result.success is True
        assert "<secret>supersecret</secret>" in posted_xml["body"]

    def test_injects_username_password_values(self):
        server = MagicMock()
        crumb_response = MagicMock()
        crumb_response.raise_for_status.return_value = None
        crumb_response.json.return_value = {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc123"}
        create_response = MagicMock()
        create_response.status_code = 200
        posted_xml = {}

        def capture_post(url, data, **kwargs):
            posted_xml["body"] = data.decode("utf-8")
            return create_response

        with (
            patch("agent.pipeline_fixes._get_jenkins_server", return_value=server),
            patch("requests.get", return_value=crumb_response),
            patch("requests.post", side_effect=capture_post),
        ):
            result = configure_credential(
                job_name="node-deploy",
                build_number="3",
                credential_id="GIT_CREDS",
                credential_type="username_password",
                username="adil",
                password="hunter2",
            )

        assert result.success is True
        assert "<username>adil</username>" in posted_xml["body"]
        assert "<password>hunter2</password>" in posted_xml["body"]

    def test_injects_ssh_key_values(self):
        server = MagicMock()
        crumb_response = MagicMock()
        crumb_response.raise_for_status.return_value = None
        crumb_response.json.return_value = {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc123"}
        create_response = MagicMock()
        create_response.status_code = 200
        posted_xml = {}

        def capture_post(url, data, **kwargs):
            posted_xml["body"] = data.decode("utf-8")
            return create_response

        with (
            patch("agent.pipeline_fixes._get_jenkins_server", return_value=server),
            patch("requests.get", return_value=crumb_response),
            patch("requests.post", side_effect=capture_post),
        ):
            result = configure_credential(
                job_name="node-deploy",
                build_number="3",
                credential_id="DEPLOY_KEY",
                credential_type="ssh_key",
                ssh_username="git",
                private_key="-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----",
            )

        assert result.success is True
        assert "<username>git</username>" in posted_xml["body"]
        assert "-----BEGIN OPENSSH PRIVATE KEY-----" in posted_xml["body"]

    def test_skip_retrigger_does_not_call_build_job(self):
        server = MagicMock()
        crumb_response = MagicMock()
        crumb_response.raise_for_status.return_value = None
        crumb_response.json.return_value = {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc123"}
        create_response = MagicMock()
        create_response.status_code = 200

        with (
            patch("agent.pipeline_fixes._get_jenkins_server", return_value=server),
            patch("requests.get", return_value=crumb_response),
            patch("requests.post", return_value=create_response),
        ):
            result = configure_credential(
                job_name="node-deploy",
                build_number="3",
                credential_id="MY_TOKEN",
                skip_retrigger=True,
            )

        assert result.success is True
        server.build_job.assert_not_called()
