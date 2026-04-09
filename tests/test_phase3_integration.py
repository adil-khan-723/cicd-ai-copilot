"""
Phase 3 integration tests — approval flow, fix execution, audit log, fallback chain.
All external calls (Jenkins API, Slack, LLM) are mocked.
"""
import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from agent.fix_executor import execute_fix
from agent.audit_log import log_fix, read_recent
from agent import audit_log as audit_log_mod
from analyzer import cache as analysis_cache
from analyzer.llm_client import analyze
from providers.factory import get_provider, ProviderUnavailableError


# ---------------------------------------------------------------------------
# Fix Executor tests
# ---------------------------------------------------------------------------

class TestFixExecutor:
    def test_diagnostic_only_never_executes(self):
        result = execute_fix("diagnostic_only", job_name="my-job")
        assert result.success is False
        assert "manual intervention" in result.detail.lower()

    def test_unknown_fix_type(self):
        result = execute_fix("magic_fix", job_name="my-job")
        assert result.success is False
        assert "Unknown" in result.detail

    @patch("agent.pipeline_fixes.jenkins.Jenkins")
    def test_retry_success(self, mock_jenkins_cls):
        mock_server = MagicMock()
        mock_jenkins_cls.return_value = mock_server

        result = execute_fix("retry", job_name="build-api", build_number="42")

        mock_server.build_job.assert_called_once_with("build-api")
        assert result.success is True
        assert "re-queued" in result.detail

    @patch("agent.pipeline_fixes.jenkins.Jenkins")
    def test_retry_jenkins_error(self, mock_jenkins_cls):
        import jenkins as jenkins_mod
        mock_server = MagicMock()
        mock_server.build_job.side_effect = jenkins_mod.JenkinsException("404 Not Found")
        mock_jenkins_cls.return_value = mock_server

        result = execute_fix("retry", job_name="missing-job")
        assert result.success is False
        assert "404" in result.detail

    @patch("agent.pipeline_fixes.jenkins.Jenkins")
    def test_clear_cache_passes_parameter(self, mock_jenkins_cls):
        mock_server = MagicMock()
        mock_jenkins_cls.return_value = mock_server

        result = execute_fix("clear_cache", job_name="build-api")
        mock_server.build_job.assert_called_once_with("build-api", parameters={"DOCKER_NO_CACHE": "true"})
        assert result.success is True

    @patch("agent.pipeline_fixes.jenkins.Jenkins")
    def test_pull_image_passes_parameter(self, mock_jenkins_cls):
        mock_server = MagicMock()
        mock_jenkins_cls.return_value = mock_server

        result = execute_fix("pull_image", job_name="build-api")
        mock_server.build_job.assert_called_once_with("build-api", parameters={"PULL_FRESH_IMAGE": "true"})
        assert result.success is True

    @patch("agent.pipeline_fixes.jenkins.Jenkins")
    def test_increase_timeout_doubles_value(self, mock_jenkins_cls):
        mock_server = MagicMock()
        mock_server.get_job_config.return_value = (
            "<project><timeout>30</timeout></project>"
        )
        mock_jenkins_cls.return_value = mock_server

        result = execute_fix("increase_timeout", job_name="build-api")

        assert result.success is True
        assert "30" in result.detail
        assert "60" in result.detail
        # Verify reconfig was called with doubled timeout
        call_args = mock_server.reconfig_job.call_args
        assert "<timeout>60</timeout>" in call_args[0][1]

    @patch("agent.pipeline_fixes.jenkins.Jenkins")
    def test_increase_timeout_no_timeout_element(self, mock_jenkins_cls):
        mock_server = MagicMock()
        mock_server.get_job_config.return_value = "<project></project>"
        mock_jenkins_cls.return_value = mock_server

        result = execute_fix("increase_timeout", job_name="build-api")
        assert result.success is False
        assert "manually" in result.detail.lower()


# ---------------------------------------------------------------------------
# Audit log tests
# ---------------------------------------------------------------------------

class TestAuditLog:
    def setup_method(self):
        # Use a temp file for each test
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        )
        self._tmp.close()
        self._path = self._tmp.name

    def teardown_method(self):
        os.unlink(self._path)

    def _patch_path(self):
        return patch.object(
            audit_log_mod.get_settings(),
            "audit_log_path",
            self._path,
        )

    def test_log_creates_entry(self):
        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._path
            log_fix("retry", "U123", "build-api", "42", "success", 0.88)

        with open(self._path) as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["fix_type"] == "retry"
        assert entry["triggered_by"] == "U123"
        assert entry["job_name"] == "build-api"
        assert entry["build_number"] == "42"
        assert entry["result"] == "success"
        assert entry["confidence_at_trigger"] == 0.88

    def test_log_appends_not_overwrites(self):
        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._path
            log_fix("retry", "U1", "job-a", "1", "success", 0.9)
            log_fix("clear_cache", "U2", "job-b", "2", "failed", 0.7)

        with open(self._path) as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_timestamp_is_utc_iso(self):
        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._path
            log_fix("retry", "U1", "job", "1", "success")

        with open(self._path) as f:
            entry = json.loads(f.readline())
        assert entry["timestamp"].endswith("+00:00")

    def test_no_secret_fields_in_entry(self):
        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._path
            log_fix("retry", "U1", "job", "1", "success")

        with open(self._path) as f:
            line = f.readline()
        # Ensure no credential-like keys snuck in
        forbidden = {"token", "secret", "password", "key", "credential"}
        entry = json.loads(line)
        for field in entry.keys():
            assert field.lower() not in forbidden, f"Sensitive field found: {field}"

    def test_read_recent_returns_entries(self):
        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._path
            for i in range(5):
                log_fix("retry", "U1", f"job-{i}", str(i), "success")

        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._path
            entries = read_recent(3)
        assert len(entries) == 3
        assert entries[-1]["job_name"] == "job-4"

    def test_read_recent_missing_file(self):
        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = "/tmp/nonexistent_audit_xyz.log"
            entries = read_recent()
        assert entries == []


# ---------------------------------------------------------------------------
# Provider fallback chain tests
# ---------------------------------------------------------------------------

class TestProviderFallback:
    def test_returns_primary_when_available(self):
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True

        with patch("providers.factory._build_provider", return_value=mock_provider):
            provider = get_provider("analysis")

        assert provider is mock_provider

    def test_falls_back_when_primary_unavailable(self):
        primary = MagicMock()
        primary.is_available.return_value = False
        fallback = MagicMock()
        fallback.is_available.return_value = True

        def build_side_effect(name, is_gen, settings):
            return primary if name == "ollama" else fallback

        with patch("providers.factory._build_provider", side_effect=build_side_effect):
            with patch("providers.factory.get_settings") as mock_settings:
                mock_settings.return_value.llm_provider = "ollama"
                mock_settings.return_value.llm_fallback_provider = "groq"
                provider = get_provider("analysis")

        assert provider is fallback

    def test_raises_when_all_providers_unavailable(self):
        unavailable = MagicMock()
        unavailable.is_available.return_value = False

        with patch("providers.factory._build_provider", return_value=unavailable):
            with patch("providers.factory.get_settings") as mock_settings:
                mock_settings.return_value.llm_provider = "ollama"
                mock_settings.return_value.llm_fallback_provider = "groq"
                with pytest.raises(ProviderUnavailableError):
                    get_provider("analysis")

    def test_skips_not_implemented_provider(self):
        fallback = MagicMock()
        fallback.is_available.return_value = True

        def build_side_effect(name, is_gen, settings):
            if name == "anthropic":
                raise NotImplementedError("not yet")
            return fallback

        with patch("providers.factory._build_provider", side_effect=build_side_effect):
            with patch("providers.factory.get_settings") as mock_settings:
                mock_settings.return_value.llm_provider = "anthropic"
                mock_settings.return_value.llm_fallback_provider = "ollama"
                provider = get_provider("analysis")

        assert provider is fallback


# ---------------------------------------------------------------------------
# Full reactive flow integration test
# ---------------------------------------------------------------------------

class TestFullReactiveFlow:
    """
    Simulates: webhook payload → parse → extract → clean → verify → context →
               LLM → Slack alert → button click → execute fix → audit log
    """

    def setup_method(self):
        analysis_cache.clear()
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        )
        self._tmp.close()

    def teardown_method(self):
        os.unlink(self._tmp.name)

    def test_full_flow_approve_fix(self):
        from parser.pipeline_parser import parse_failure
        from parser.log_extractor import extract_failed_logs
        from parser.log_cleaner import clean_log
        from analyzer.context_builder import build_context
        from verification.models import VerificationReport

        payload = {
            "job_name": "build-api",
            "build_number": 42,
            "branch": "main",
            "log": (
                "[Pipeline] stage (Checkout)\n"
                "[INFO] Cloning...\n"
                "[Pipeline] stage (Docker Build)\n"
                "ERROR: Could not find a version that satisfies fastapi==99.0.0\n"
                "[Pipeline] stage (Test)\n"
                "[INFO] Skipped\n"
            ),
        }

        # Parse
        ctx = parse_failure(payload, source="jenkins")
        assert ctx.failed_stage == "Docker Build"

        # Extract + clean
        extracted = extract_failed_logs(ctx)
        cleaned = clean_log(extracted)
        assert "fastapi==99.0.0" in cleaned

        # Verification (empty — no live Jenkins)
        report = VerificationReport(platform="jenkins")

        # Context
        context_str = build_context(cleaned, report, ctx)
        assert "build-api" in context_str

        # LLM analysis (mocked)
        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.is_available.return_value = True
        mock_provider.complete.return_value = (
            '{"root_cause": "pip dep conflict", "fix_suggestion": "Pin fastapi", '
            '"confidence": 0.9, "fix_type": "clear_cache"}'
        )

        with patch("analyzer.llm_client.get_provider", return_value=mock_provider):
            analysis = analyze(context_str)

        assert analysis["fix_type"] == "clear_cache"

        # Fix execution (mocked Jenkins)
        with patch("agent.pipeline_fixes.jenkins.Jenkins") as mock_jenkins_cls:
            mock_server = MagicMock()
            mock_jenkins_cls.return_value = mock_server
            result = execute_fix(analysis["fix_type"], job_name=ctx.job_name)

        assert result.success is True

        # Audit log
        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._tmp.name
            log_fix(
                fix_type=analysis["fix_type"],
                triggered_by="U_ADIL",
                job_name=ctx.job_name,
                build_number=ctx.build_number,
                result="success" if result.success else "failed",
                confidence_at_trigger=analysis["confidence"],
            )

        with patch("agent.audit_log.get_settings") as mock_settings:
            mock_settings.return_value.audit_log_path = self._tmp.name
            entries = read_recent(1)

        assert len(entries) == 1
        assert entries[0]["fix_type"] == "clear_cache"
        assert entries[0]["triggered_by"] == "U_ADIL"
        assert entries[0]["result"] == "success"
