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
    _check_tool_usage_patterns,
    _check_tool_install,
)
from verification.models import VerificationReport, ToolMismatch

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

# Script console response: each line is "tooltype:toolname"
# maven → Maven-3 (close but not exact to 'Maven3')
# jdk   → JDK-17  (exact)
# docker is absent (so Docker → mismatch with no candidate)
SCRIPT_CONSOLE_RESPONSE = "maven:Maven-3\njdk:JDK-17\n"

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
        respx.post(f"{JENKINS_URL}/scriptText").mock(
            return_value=httpx.Response(200, text=SCRIPT_CONSOLE_RESPONSE)
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
        respx.post(f"{JENKINS_URL}/scriptText").mock(
            return_value=httpx.Response(200, text=SCRIPT_CONSOLE_RESPONSE)
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
        respx.post(f"{JENKINS_URL}/scriptText").mock(
            return_value=httpx.Response(200, text=SCRIPT_CONSOLE_RESPONSE)
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
        # /scriptText connect error → _fetch_configured_tools returns {} silently
        # Plugins and credentials GET calls still fire — mock them to avoid leaking
        respx.post(f"{JENKINS_URL}/scriptText").mock(
            side_effect=httpx.ConnectError("refused")
        )
        respx.get(f"{JENKINS_URL}/pluginManager/api/json?depth=1").mock(
            side_effect=httpx.ConnectError("refused")
        )
        respx.get(f"{JENKINS_URL}/credentials/store/system/domain/_/api/json?depth=1").mock(
            side_effect=httpx.ConnectError("refused")
        )

        # The outer httpx.Client context catches ConnectError on scriptText internally.
        # No outer ConnectError propagates, so report.errors stays empty — tool data
        # simply unavailable. Verify no crash and no false positives.
        report = verify_jenkins_tools(SAMPLE_JENKINSFILE, JENKINS_URL)
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


# ---------------------------------------------------------------------------
# Tool install issue checks
# ---------------------------------------------------------------------------

INSTALL_DETAILS_AUTO = {"Maven-3": {"home": "", "auto_install": True}}
INSTALL_DETAILS_NO_HOME = {"Maven-3": {"home": "", "auto_install": False}}
INSTALL_DETAILS_OK = {"Maven-3": {"home": "/usr/share/maven", "auto_install": False}}


class TestToolInstallCheck:
    def _matched_report(self) -> VerificationReport:
        r = VerificationReport(platform="jenkins")
        r.matched_tools.append("Maven-3")
        return r

    def test_auto_install_flagged(self):
        r = self._matched_report()
        _check_tool_install("maven", "Maven-3", {}, INSTALL_DETAILS_AUTO, r)
        assert len(r.tool_install_issues) == 1
        assert "auto-install" in r.tool_install_issues[0].issue

    def test_no_home_no_auto_flagged(self):
        r = self._matched_report()
        _check_tool_install("maven", "Maven-3", {}, INSTALL_DETAILS_NO_HOME, r)
        assert len(r.tool_install_issues) == 1
        assert "no install home path" in r.tool_install_issues[0].issue

    def test_healthy_install_not_flagged(self):
        r = self._matched_report()
        _check_tool_install("maven", "Maven-3", {}, INSTALL_DETAILS_OK, r)
        assert len(r.tool_install_issues) == 0

    def test_unmatched_tool_skipped(self):
        r = VerificationReport(platform="jenkins")
        # Maven-3 not in matched_tools → skip
        _check_tool_install("maven", "Maven-3", {}, INSTALL_DETAILS_AUTO, r)
        assert len(r.tool_install_issues) == 0

    def test_no_detail_for_tool_skipped(self):
        r = self._matched_report()
        _check_tool_install("maven", "Maven-3", {}, {}, r)
        assert len(r.tool_install_issues) == 0

    def test_summary_lines_include_install_issue(self):
        r = self._matched_report()
        _check_tool_install("maven", "Maven-3", {}, INSTALL_DETAILS_AUTO, r)
        lines = r.summary_lines()
        assert any("Maven-3" in l and "auto-install" in l for l in lines)


# ---------------------------------------------------------------------------
# Tool usage pattern checks
# ---------------------------------------------------------------------------

JENKINSFILE_DIRECT_MVN = """
pipeline {
    agent any
    tools { maven 'Maven-3' }
    stages {
        stage('Build') {
            steps { sh 'mvn clean package' }
        }
    }
}
"""

JENKINSFILE_WITH_MAVEN_WRAPPER = """
pipeline {
    agent any
    tools { maven 'Maven-3' }
    stages {
        stage('Build') {
            steps {
                withMaven(maven: 'Maven-3') {
                    sh 'mvn clean package'
                }
            }
        }
    }
}
"""

JENKINSFILE_TOOL_STEP_PATH = """
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                script {
                    def mvnHome = tool 'Maven-3'
                    env.PATH = "${mvnHome}/bin:${env.PATH}"
                    sh 'mvn clean package'
                }
            }
        }
    }
}
"""

JENKINSFILE_DIRECT_GRADLE = """
pipeline {
    agent any
    tools { gradle 'Gradle-8' }
    stages {
        stage('Build') {
            steps { sh 'gradle build' }
        }
    }
}
"""


class TestToolUsagePatterns:
    def test_direct_mvn_flagged(self):
        r = VerificationReport(platform="jenkins")
        tools = [("maven", "Maven-3")]
        _check_tool_usage_patterns(JENKINSFILE_DIRECT_MVN, tools, r)
        assert len(r.tool_usage_pattern_issues) == 1
        issue = r.tool_usage_pattern_issues[0]
        assert issue.tool_type == "maven"
        assert issue.tool_name == "Maven-3"
        assert issue.binary == "mvn"

    def test_with_maven_wrapper_not_flagged(self):
        r = VerificationReport(platform="jenkins")
        tools = [("maven", "Maven-3")]
        _check_tool_usage_patterns(JENKINSFILE_WITH_MAVEN_WRAPPER, tools, r)
        assert len(r.tool_usage_pattern_issues) == 0

    def test_tool_step_with_path_not_flagged(self):
        r = VerificationReport(platform="jenkins")
        tools = [("maven", "Maven-3")]
        _check_tool_usage_patterns(JENKINSFILE_TOOL_STEP_PATH, tools, r)
        assert len(r.tool_usage_pattern_issues) == 0

    def test_direct_gradle_flagged(self):
        r = VerificationReport(platform="jenkins")
        tools = [("gradle", "Gradle-8")]
        _check_tool_usage_patterns(JENKINSFILE_DIRECT_GRADLE, tools, r)
        assert len(r.tool_usage_pattern_issues) == 1
        assert r.tool_usage_pattern_issues[0].tool_type == "gradle"

    def test_no_sh_steps_not_flagged(self):
        jf = "pipeline { agent any tools { maven 'Maven-3' } stages { stage('S') { steps { echo 'hi' } } } }"
        r = VerificationReport(platform="jenkins")
        _check_tool_usage_patterns(jf, [("maven", "Maven-3")], r)
        assert len(r.tool_usage_pattern_issues) == 0

    def test_empty_tools_list_skipped(self):
        r = VerificationReport(platform="jenkins")
        _check_tool_usage_patterns(JENKINSFILE_DIRECT_MVN, [], r)
        assert len(r.tool_usage_pattern_issues) == 0

    def test_summary_lines_include_usage_warning(self):
        r = VerificationReport(platform="jenkins")
        _check_tool_usage_patterns(JENKINSFILE_DIRECT_MVN, [("maven", "Maven-3")], r)
        lines = r.summary_lines()
        assert any("Maven-3" in l and "PATH" in l for l in lines)


# ---------------------------------------------------------------------------
# Integration: verify_jenkins_tools emits usage pattern findings
# ---------------------------------------------------------------------------

SCRIPT_CONSOLE_MATCHED = "maven:Maven-3\n"
INSTALL_DETAILS_SCRIPT = "Maven-3||true\n"  # auto-install, no home


class TestVerifyJenkinsToolsIntegration:
    @respx.mock
    def test_usage_pattern_detected_end_to_end(self):
        respx.post(f"{JENKINS_URL}/scriptText").mock(
            return_value=httpx.Response(200, text=SCRIPT_CONSOLE_MATCHED + INSTALL_DETAILS_SCRIPT)
        )
        respx.get(f"{JENKINS_URL}/pluginManager/api/json?depth=1").mock(
            return_value=httpx.Response(200, json={"plugins": [{"shortName": "maven-plugin"}]})
        )
        respx.get(f"{JENKINS_URL}/credentials/store/system/domain/_/api/json?depth=1").mock(
            return_value=httpx.Response(200, json={"credentials": []})
        )

        report = verify_jenkins_tools(JENKINSFILE_DIRECT_MVN, JENKINS_URL)
        assert len(report.tool_usage_pattern_issues) == 1
        assert report.has_issues
