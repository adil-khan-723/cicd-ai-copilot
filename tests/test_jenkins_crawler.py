"""
Unit tests for Jenkins Tool Verification Crawler (Increment 12).
Jenkins API calls are mocked — no live Jenkins required.
"""
import pytest
import respx
import httpx

from verification.jenkins_crawler import (
    verify_jenkins_tools,
    _parse_tools_block,
    _parse_credentials,
)

JENKINS_URL = "http://jenkins.local:8080"

SAMPLE_JENKINSFILE = """
pipeline {
    agent any
    tools {
        maven 'Maven3'
        jdk 'JDK-17'
        docker 'Docker'
    }
    stages {
        stage('Build') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'ECR_CREDENTIALS',
                    usernameVariable: 'USER',
                    passwordVariable: 'PASS'
                )]) {
                    sh 'mvn clean package'
                }
            }
        }
        stage('Deploy') {
            steps {
                sh 'docker push ${credentials("DEPLOY_KEY")}'
            }
        }
    }
}
"""

CONFIGURED_TOOLS_RESPONSE = {
    "tools": [
        {"name": "Maven-3"},       # close but not exact to 'Maven3'
        {"name": "JDK-17"},        # exact
        {"name": "Docker-Latest"},  # not close to 'Docker'
    ]
}

PLUGINS_RESPONSE = {
    "plugins": [
        {"shortName": "maven-plugin"},
        {"shortName": "git"},
        # docker-plugin intentionally missing
    ]
}

CREDENTIALS_RESPONSE = {
    "credentials": [
        {"id": "ECR_CREDENTIALS"},
        # DEPLOY_KEY intentionally missing
    ]
}


class TestParseToolsBlock:
    def test_extracts_all_tools(self):
        tools = _parse_tools_block(SAMPLE_JENKINSFILE)
        assert ("maven", "Maven3") in tools
        assert ("jdk", "JDK-17") in tools
        assert ("docker", "Docker") in tools

    def test_no_tools_block(self):
        assert _parse_tools_block("pipeline { agent any }") == []


class TestParseCredentials:
    def test_extracts_credentials_id(self):
        creds = _parse_credentials(SAMPLE_JENKINSFILE)
        assert "ECR_CREDENTIALS" in creds
        assert "DEPLOY_KEY" in creds

    def test_deduplicates(self):
        content = "credentials('X') credentials('X')"
        creds = _parse_credentials(content)
        assert creds.count("X") == 1

    def test_no_credentials(self):
        assert _parse_credentials("pipeline {}") == []


class TestVerifyJenkinsTools:
    @respx.mock
    def test_detects_tool_mismatch(self):
        respx.get(f"{JENKINS_URL}/api/json?depth=2").mock(
            return_value=httpx.Response(200, json=CONFIGURED_TOOLS_RESPONSE)
        )
        respx.get(f"{JENKINS_URL}/pluginManager/api/json?depth=1").mock(
            return_value=httpx.Response(200, json=PLUGINS_RESPONSE)
        )
        respx.get(f"{JENKINS_URL}/credentials/store/system/domain/_/api/json?depth=1").mock(
            return_value=httpx.Response(200, json=CREDENTIALS_RESPONSE)
        )

        report = verify_jenkins_tools(SAMPLE_JENKINSFILE, JENKINS_URL)

        # JDK-17 exact match → matched
        assert "JDK-17" in report.matched_tools

        # Maven3 vs Maven-3 → mismatch (close but not exact)
        mismatch_names = [m.referenced for m in report.mismatched_tools]
        assert "Maven3" in mismatch_names

    @respx.mock
    def test_detects_missing_credentials(self):
        respx.get(f"{JENKINS_URL}/api/json?depth=2").mock(
            return_value=httpx.Response(200, json=CONFIGURED_TOOLS_RESPONSE)
        )
        respx.get(f"{JENKINS_URL}/pluginManager/api/json?depth=1").mock(
            return_value=httpx.Response(200, json=PLUGINS_RESPONSE)
        )
        respx.get(f"{JENKINS_URL}/credentials/store/system/domain/_/api/json?depth=1").mock(
            return_value=httpx.Response(200, json=CREDENTIALS_RESPONSE)
        )

        report = verify_jenkins_tools(SAMPLE_JENKINSFILE, JENKINS_URL)
        assert "DEPLOY_KEY" in report.missing_credentials
        assert "ECR_CREDENTIALS" not in report.missing_credentials

    @respx.mock
    def test_detects_missing_plugin(self):
        respx.get(f"{JENKINS_URL}/api/json?depth=2").mock(
            return_value=httpx.Response(200, json=CONFIGURED_TOOLS_RESPONSE)
        )
        respx.get(f"{JENKINS_URL}/pluginManager/api/json?depth=1").mock(
            return_value=httpx.Response(200, json=PLUGINS_RESPONSE)
        )
        respx.get(f"{JENKINS_URL}/credentials/store/system/domain/_/api/json?depth=1").mock(
            return_value=httpx.Response(200, json=CREDENTIALS_RESPONSE)
        )

        report = verify_jenkins_tools(SAMPLE_JENKINSFILE, JENKINS_URL)
        assert "docker-plugin" in report.missing_plugins
        assert "maven-plugin" not in report.missing_plugins

    @respx.mock
    def test_connect_error_recorded(self):
        respx.get(f"{JENKINS_URL}/api/json?depth=2").mock(
            side_effect=httpx.ConnectError("refused")
        )

        report = verify_jenkins_tools(SAMPLE_JENKINSFILE, JENKINS_URL)
        assert any("Cannot reach Jenkins" in e for e in report.errors)
        assert not report.has_issues

    @respx.mock
    def test_empty_jenkinsfile(self):
        report = verify_jenkins_tools("pipeline { agent any }", JENKINS_URL)
        assert not report.has_issues
        assert not report.errors

    def test_has_issues_property(self):
        from verification.models import VerificationReport, ToolMismatch
        report = VerificationReport(platform="jenkins")
        assert not report.has_issues
        report.missing_credentials.append("MY_CRED")
        assert report.has_issues

    def test_summary_lines(self):
        from verification.models import VerificationReport, ToolMismatch
        report = VerificationReport(platform="jenkins")
        report.mismatched_tools.append(ToolMismatch("Maven3", "Maven-3", 0.91))
        report.missing_credentials.append("ECR_CREDENTIALS")
        lines = report.summary_lines()
        assert any("Maven3" in l for l in lines)
        assert any("ECR_CREDENTIALS" in l for l in lines)
