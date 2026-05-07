import pytest
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient
from webhook.server import app

MOCK_PAYLOAD = {
    "job_name": "test-job",
    "build_number": "1",
    "failed_stage": "Build",
    "status": "FAILURE",
    "stages": [{"name": "Build", "status": "failed"}],
    "log": "error: command not found",
}


def test_analysis_complete_includes_verification():
    """analysis_complete SSE event must include a verification key with all VerificationReport fields."""
    from ui.event_bus import bus

    published = []
    original_publish = bus.publish

    def capture(event):
        published.append(event)
        original_publish(event)

    mock_provider = MagicMock()
    mock_provider.complete.return_value = '{"root_cause":"test","fix_suggestion":"retry","fix_type":"retry","confidence":0.9}'

    with patch.object(bus, "publish", side_effect=capture), \
         patch("analyzer.llm_client.get_provider", return_value=mock_provider), \
         patch("webhook.server._run_verification") as mock_verify:
        from verification.models import VerificationReport
        mock_verify.return_value = VerificationReport(
            platform="jenkins",
            missing_credentials=["MY_SECRET"],
        )
        from webhook.server import _process_failure_sync
        _process_failure_sync(MOCK_PAYLOAD, "jenkins")

    analysis_events = [e for e in published if e.get("type") == "analysis_complete"]
    assert len(analysis_events) == 1
    ev = analysis_events[0]
    assert "verification" in ev
    v = ev["verification"]
    assert "matched_tools" in v
    assert "mismatched_tools" in v
    assert "missing_plugins" in v
    assert "missing_credentials" in v
    assert "missing_secrets" in v
    assert "missing_runners" in v
    assert "unpinned_actions" in v
    assert "errors" in v
    assert "MY_SECRET" in v["missing_credentials"]


# ── Stage detection regression tests ─────────────────────────────────────────

REAL_LOG_STAGE_FAIL = """Started by user admin
[Pipeline] Start of Pipeline
[Pipeline] node
Running on Jenkins
[Pipeline] {
[Pipeline] stage
[Pipeline] { (Checkout)
[Pipeline] echo
Checking out code...
[Pipeline] sh
+ echo checkout done
checkout done
[Pipeline] }
[Pipeline] // stage
[Pipeline] stage
[Pipeline] { (Build)
[Pipeline] echo
Building...
[Pipeline] sh
+ nonexistent-command --version
/var/jenkins_home/workspace/stage-fail-test@tmp/script.sh: 1: nonexistent-command: not found
[Pipeline] }
[Pipeline] // stage
[Pipeline] stage
[Pipeline] { (Test)
Stage "Test" skipped due to earlier failure(s)
[Pipeline] getContext
[Pipeline] }
[Pipeline] // stage
[Pipeline] }
[Pipeline] // node
[Pipeline] End of Pipeline
ERROR: script returned exit code 127
Finished: FAILURE"""


def test_detect_stages_block_aware():
    """Build fails → Test must be skipped, not failed. Global ERROR must not pollute skipped stages."""
    from webhook.server import _detect_stages
    stages = _detect_stages(REAL_LOG_STAGE_FAIL)
    by_name = {s["name"]: s["status"] for s in stages}
    assert by_name["Checkout"] == "passed", f"Checkout should be passed, got {by_name['Checkout']}"
    assert by_name["Build"]    == "failed", f"Build should be failed, got {by_name['Build']}"
    assert by_name["Test"]     == "skipped", f"Test should be skipped, got {by_name['Test']}"


def test_detect_failed_stage_block_aware():
    """_detect_failed_stage returns the stage whose own block contains the error."""
    from webhook.server import _detect_failed_stage
    assert _detect_failed_stage(REAL_LOG_STAGE_FAIL) == "Build"


def test_detect_stages_all_pass():
    """All stages passed — none should be marked failed or skipped."""
    from webhook.server import _detect_stages
    log = """[Pipeline] { (Checkout)
+ echo done
checkout done
[Pipeline] }
[Pipeline] { (Build)
+ mvn install
BUILD SUCCESS
[Pipeline] }
[Pipeline] { (Test)
Tests run: 10, Failures: 0
[Pipeline] }"""
    stages = _detect_stages(log)
    for s in stages:
        assert s["status"] == "passed", f"{s['name']} should be passed"


def test_detect_stages_skipped_after_fail():
    """All stages after the failed one must be skipped, even if they have no error text."""
    from webhook.server import _detect_stages
    log = """[Pipeline] { (Checkout)
checkout done
[Pipeline] }
[Pipeline] { (Build)
error: compilation failed
[Pipeline] }
[Pipeline] { (Test)
Stage "Test" skipped due to earlier failure(s)
[Pipeline] }
[Pipeline] { (Deploy)
Stage "Deploy" skipped due to earlier failure(s)
[Pipeline] }"""
    stages = _detect_stages(log)
    by_name = {s["name"]: s["status"] for s in stages}
    assert by_name["Checkout"] == "passed"
    assert by_name["Build"]    == "failed"
    assert by_name["Test"]     == "skipped"
    assert by_name["Deploy"]   == "skipped"


def test_notification_failure_fetches_jenkinsfile():
    """Synthetic payload must include jenkinsfile so tool crawler runs."""
    from unittest.mock import patch, MagicMock
    from webhook.server import _process_notification_failure_sync

    mock_server = MagicMock()
    mock_server.get_build_console_output.return_value = (
        "[Pipeline] { (Test)\nERROR: test failed\n[Pipeline] }"
    )
    mock_server.get_job_config.return_value = """<?xml version='1.1'?>
<flow-definition>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition">
    <script>pipeline { agent any; stages { stage('Test') { steps { sh 'pytest' } } } }</script>
  </definition>
</flow-definition>"""

    captured = {}

    def fake_process(payload, source):
        captured['payload'] = payload

    mock_settings = MagicMock()
    mock_settings.jenkins_url = "http://jenkins:8080"
    mock_settings.jenkins_user = "admin"
    mock_settings.jenkins_token = "test-token"

    with patch('jenkins.Jenkins', return_value=mock_server), \
         patch('webhook.server.get_settings', return_value=mock_settings), \
         patch('webhook.server._process_failure_sync', side_effect=fake_process):
        _process_notification_failure_sync("my-job", "42", {})

    assert 'jenkinsfile' in captured.get('payload', {}), \
        "Synthetic payload must contain jenkinsfile key"
    assert "pipeline {" in captured['payload']['jenkinsfile']


def test_cache_cleared_on_startup():
    """Cache must be cleared every time the app starts up."""
    with patch("analyzer.cache.clear_all") as mock_clear:
        with TestClient(app):
            mock_clear.assert_called_once()


class TestFilterPotentialIssues:
    def test_filter_config_issue_confirmed_by_crawler(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport, ToolMismatch
        report = VerificationReport(platform="jenkins")
        report.mismatched_tools.append(ToolMismatch(referenced="Maven-3", configured="Maven3", match_score=0.91))
        issues = [{"type": "config", "line": "maven 'Maven-3'", "issue": "Tool mismatch", "fix_type": "configure_tool"}]
        result = _filter_potential_issues(issues, report)
        assert len(result) == 1
        assert result[0]["confidence"] == "confirmed"

    def test_filter_config_issue_contradicted_by_crawler_dropped(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        report.matched_tools.append("Maven3")
        issues = [{"type": "config", "line": "maven 'Maven3'", "issue": "Tool mismatch", "fix_type": "configure_tool"}]
        result = _filter_potential_issues(issues, report)
        assert len(result) == 0

    def test_filter_missing_credential_confirmed(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        report.missing_credentials.append("aws-prod")
        issues = [{"type": "config", "line": "credentials('aws-prod')", "issue": "Missing cred", "fix_type": "configure_credential"}]
        result = _filter_potential_issues(issues, report)
        assert len(result) == 1
        assert result[0]["confidence"] == "confirmed"

    def test_filter_syntax_issue_passes_through_as_llm_only(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        issues = [{"type": "syntax", "line": "sh 'mvn clen install'", "issue": "Typo", "fix_type": "fix_step_typo"}]
        result = _filter_potential_issues(issues, report)
        assert len(result) == 1
        assert result[0]["confidence"] == "llm_only"

    def test_filter_logic_issue_passes_through_as_llm_only(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        issues = [{"type": "logic", "line": "sh 'docker push $IMAGE'", "issue": "Unset var", "fix_type": "logic_error"}]
        result = _filter_potential_issues(issues, report)
        assert len(result) == 1
        assert result[0]["confidence"] == "llm_only"

    def test_filter_dedup_removes_primary_fix_match(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        report.missing_credentials.append("aws-prod")
        issues = [{"type": "config", "line": "credentials('aws-prod')", "issue": "Missing cred", "fix_type": "configure_credential"}]
        result = _filter_potential_issues(issues, report, primary_fix_type="configure_credential", primary_cred_id="aws-prod")
        assert len(result) == 0

    def test_filter_live_api_confirms_missing_cred_when_crawler_silent(self):
        """Crawler didn't list it but live API says it doesn't exist → confirmed."""
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        issues = [{"type": "config", "line": "credentialsId: 'aws-prod-key'", "issue": "Missing cred", "fix_type": "configure_credential"}]
        with patch("verification.jenkins_crawler.credential_exists", return_value=False):
            result = _filter_potential_issues(issues, report, jenkins_url="http://j", jenkins_auth=("u","t"))
        assert len(result) == 1
        assert result[0]["confidence"] == "confirmed"
        assert result[0]["credential_id"] == "aws-prod-key"

    def test_filter_live_api_drops_cred_that_actually_exists(self):
        """Crawler silent + live API confirms cred exists → drop."""
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        issues = [{"type": "config", "line": "credentialsId: 'real-cred'", "issue": "Missing cred", "fix_type": "configure_credential"}]
        with patch("verification.jenkins_crawler.credential_exists", return_value=True):
            result = _filter_potential_issues(issues, report, jenkins_url="http://j", jenkins_auth=("u","t"))
        assert len(result) == 0

    def test_filter_live_api_unreachable_keeps_unverified(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        issues = [{"type": "config", "line": "credentialsId: 'unknown'", "issue": "Missing cred", "fix_type": "configure_credential"}]
        with patch("verification.jenkins_crawler.credential_exists", return_value=None):
            result = _filter_potential_issues(issues, report, jenkins_url="http://j", jenkins_auth=("u","t"))
        assert len(result) == 1
        assert result[0]["confidence"] == "unverified"

    def test_filter_live_api_confirms_missing_tool(self):
        from webhook.server import _filter_potential_issues
        from verification.models import VerificationReport
        report = VerificationReport(platform="jenkins")
        issues = [{"type": "config", "line": "tool name: 'Maven3'", "issue": "Tool missing", "fix_type": "configure_tool"}]
        with patch("verification.jenkins_crawler.tool_exists", return_value=False):
            result = _filter_potential_issues(issues, report, jenkins_url="http://j", jenkins_auth=("u","t"))
        assert len(result) == 1
        assert result[0]["confidence"] == "confirmed"
        assert result[0]["tool_ref"] == "Maven3"
