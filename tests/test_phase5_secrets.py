"""
Phase 5 tests — Secrets management, scrubber, startup security checker,
test-connection endpoint, audit wiring, settings endpoint expansion.
All external calls are mocked.
"""
import json
import pytest
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# TestScrubber
# ---------------------------------------------------------------------------

class TestScrubber:
    def setup_method(self):
        from copilot.secrets_manager import scrub
        self.scrub = scrub

    def test_scrubs_anthropic_key(self):
        text = "Error: key=sk-ant-api03-AbcDefGhi12345678901234"
        result = self.scrub(text)
        assert "sk-ant-" not in result
        assert "[REDACTED:anthropic-key]" in result

    def test_scrubs_github_pat_new(self):
        text = "token=github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789012"
        result = self.scrub(text)
        assert "github_pat_" not in result
        assert "[REDACTED:github-pat]" in result

    def test_scrubs_github_pat_old(self):
        text = "Authorization: token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234567890"
        result = self.scrub(text)
        assert "ghp_" not in result
        assert "[REDACTED:github-token]" in result

    def test_scrubs_jenkins_token(self):
        text = "auth failed for token 11cd58e68141b56335db245374772fc1"
        result = self.scrub(text)
        assert "11cd58e68141b56335db245374772fc1" not in result
        assert "[REDACTED:jenkins-token]" in result

    def test_scrubs_aws_key(self):
        text = "AWS key AKIAIOSFODNN7EXAMPLE was exposed"
        result = self.scrub(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED:aws-key]" in result

    def test_scrubs_bearer_header(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = self.scrub(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer [REDACTED]" in result

    def test_scrubs_basic_auth(self):
        text = "Authorization: Basic YWRtaW46cGFzc3dvcmQ="
        result = self.scrub(text)
        assert "YWRtaW46cGFzc3dvcmQ=" not in result
        assert "Basic [REDACTED]" in result

    def test_passthrough_clean_text(self):
        text = "Build failed at stage Docker Build — exit code 1"
        assert self.scrub(text) == text

    def test_none_passthrough(self):
        assert self.scrub(None) is None  # type: ignore[arg-type]

    def test_empty_string_passthrough(self):
        assert self.scrub("") == ""

    def test_scrubs_multiple_patterns(self):
        text = (
            "key=sk-ant-api03-AbcDefGhi12345678901234 "
            "and ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234567890"
        )
        result = self.scrub(text)
        assert "[REDACTED:anthropic-key]" in result
        assert "[REDACTED:github-token]" in result
        assert "sk-ant-" not in result
        assert "ghp_" not in result

    def test_jenkins_token_boundary_31_chars_not_scrubbed(self):
        # 31 hex chars — must NOT be matched
        text = "ref=1234567890abcdef1234567890abc"
        result = self.scrub(text)
        assert result == text

    def test_jenkins_token_boundary_32_chars_scrubbed(self):
        # Exactly 32 hex chars — must be matched
        tok = "1234567890abcdef1234567890abcdef"  # 32 chars
        assert len(tok) == 32
        text = f"token {tok}"
        result = self.scrub(text)
        assert tok not in result
        assert "[REDACTED:jenkins-token]" in result


# ---------------------------------------------------------------------------
# TestStartupSecurityChecker
# ---------------------------------------------------------------------------

class TestStartupSecurityChecker:
    def setup_method(self):
        from copilot.secrets_manager import check_startup_security
        self.check = check_startup_security

    def _make_settings(self, webhook_secret="abc", jenkins_token="tok", anthropic_api_key="", log_level="INFO"):
        s = MagicMock()
        s.webhook_secret = webhook_secret
        s.jenkins_token = jenkins_token
        s.anthropic_api_key = anthropic_api_key
        s.log_level = log_level
        return s

    def test_empty_webhook_secret_produces_warning(self):
        s = self._make_settings(webhook_secret="")
        warnings = self.check(s)
        assert any("WEBHOOK_SECRET" in w for w in warnings)

    def test_set_webhook_secret_no_webhook_warning(self):
        s = self._make_settings(webhook_secret="mysecret")
        warnings = self.check(s)
        assert not any("WEBHOOK_SECRET" in w for w in warnings)

    def test_empty_jenkins_token_produces_warning(self):
        s = self._make_settings(jenkins_token="")
        warnings = self.check(s)
        assert any("JENKINS_TOKEN" in w for w in warnings)

    def test_debug_level_with_api_key_produces_warning(self):
        s = self._make_settings(anthropic_api_key="sk-ant-key123", log_level="DEBUG")
        warnings = self.check(s)
        assert any("DEBUG" in w for w in warnings)

    def test_all_clean_no_warnings(self):
        s = self._make_settings(webhook_secret="secret", jenkins_token="token", anthropic_api_key="", log_level="INFO")
        warnings = self.check(s)
        assert warnings == []


# ---------------------------------------------------------------------------
# TestWarnSecurityConfig
# ---------------------------------------------------------------------------

class TestWarnSecurityConfig:
    def test_warns_on_empty_webhook_secret(self):
        from config.validator import warn_security_config
        s = MagicMock()
        s.webhook_secret = ""
        s.jenkins_token = "tok"
        s.anthropic_api_key = ""
        s.log_level = "INFO"
        with patch("config.validator.logger") as mock_log:
            warn_security_config(s)
        assert mock_log.warning.called

    def test_never_raises(self):
        from config.validator import warn_security_config
        s = MagicMock()
        s.webhook_secret = ""
        s.jenkins_token = ""
        s.anthropic_api_key = "sk-ant-key"
        s.log_level = "DEBUG"
        # Must not raise under any combination
        warn_security_config(s)


# ---------------------------------------------------------------------------
# TestTestConnectionEndpoint
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from webhook.server import app
    return TestClient(app, raise_server_exceptions=False)


class TestTestConnectionEndpoint:
    def test_jenkins_ok_returns_ok_true(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("config.settings._settings", None), \
             patch("config.settings.Settings") as MockSettings, \
             patch("requests.get", return_value=mock_resp):
            s = MagicMock()
            s.jenkins_url = "http://jenkins:8080"
            s.jenkins_user = "admin"
            s.jenkins_token = "abc123"
            s.llm_provider = "ollama"
            s.llm_fallback_provider = ""
            MockSettings.return_value = s
            r = client.post("/api/secrets/test-connection", json={"provider": "jenkins"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_jenkins_fail_returns_ok_false(self, client):
        with patch("config.settings._settings", None), \
             patch("config.settings.Settings") as MockSettings, \
             patch("requests.get", side_effect=Exception("Connection refused")):
            s = MagicMock()
            s.jenkins_url = "http://jenkins:8080"
            s.jenkins_user = "admin"
            s.jenkins_token = "abc123"
            MockSettings.return_value = s
            r = client.post("/api/secrets/test-connection", json={"provider": "jenkins"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "detail" in data

    def test_jenkins_not_configured_returns_ok_false(self, client):
        with patch("config.settings._settings", None), \
             patch("config.settings.Settings") as MockSettings:
            s = MagicMock()
            s.jenkins_url = ""
            s.jenkins_token = ""
            s.jenkins_user = ""
            MockSettings.return_value = s
            r = client.post("/api/secrets/test-connection", json={"provider": "jenkins"})
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_jenkins_error_detail_scrubbed(self, client):
        token = "11cd58e68141b56335db245374772fc1"
        with patch("config.settings._settings", None), \
             patch("config.settings.Settings") as MockSettings, \
             patch("requests.get", side_effect=Exception(f"auth failed token={token}")):
            s = MagicMock()
            s.jenkins_url = "http://jenkins:8080"
            s.jenkins_user = "admin"
            s.jenkins_token = token
            MockSettings.return_value = s
            r = client.post("/api/secrets/test-connection", json={"provider": "jenkins"})
        assert token not in r.json().get("detail", "")
        assert "[REDACTED" in r.json().get("detail", "")

    def test_anthropic_ok(self, client):
        with patch("providers.anthropic_provider.AnthropicProvider.is_available", return_value=True):
            r = client.post("/api/secrets/test-connection", json={"provider": "anthropic"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_anthropic_fail(self, client):
        with patch("providers.anthropic_provider.AnthropicProvider.is_available", return_value=False):
            r = client.post("/api/secrets/test-connection", json={"provider": "anthropic"})
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_ollama_provider(self, client):
        with patch("providers.ollama_provider.OllamaProvider.is_available", return_value=True):
            r = client.post("/api/secrets/test-connection", json={"provider": "ollama"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_unknown_provider(self, client):
        r = client.post("/api/secrets/test-connection", json={"provider": "vault"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "Unknown provider" in data["detail"]


# ---------------------------------------------------------------------------
# TestAuditWiring
# ---------------------------------------------------------------------------

class TestAuditWiring:
    def test_get_jenkins_server_calls_audit(self):
        from agent import pipeline_fixes
        with patch("agent.pipeline_fixes.get_settings") as mock_gs, \
             patch("agent.pipeline_fixes.jenkins.Jenkins") as mock_jenkins, \
             patch("agent.pipeline_fixes.audit_secret_used") as mock_audit:
            s = MagicMock()
            s.jenkins_url = "http://jenkins:8080"
            s.jenkins_user = "admin"
            s.jenkins_token = "tok"
            mock_gs.return_value = s
            pipeline_fixes._get_jenkins_server()
        mock_audit.assert_called_once_with("system", "jenkins_token")

    def test_anthropic_get_client_calls_audit_once(self):
        from providers.anthropic_provider import AnthropicProvider
        with patch("providers.anthropic_provider.anthropic_sdk.Anthropic"), \
             patch("providers.anthropic_provider.get_settings") as mock_gs, \
             patch("copilot.secrets_manager.audit_secret_used") as mock_audit:
            s = MagicMock()
            s.anthropic_api_key = "sk-ant-key"
            s.anthropic_analysis_model = "claude-haiku-4-5-20251001"
            mock_gs.return_value = s

            provider = AnthropicProvider()
            provider._get_client()
        mock_audit.assert_called_once_with("system", "anthropic_api_key")

    def test_anthropic_get_client_audit_fires_only_once_on_repeat_calls(self):
        from providers.anthropic_provider import AnthropicProvider
        with patch("providers.anthropic_provider.anthropic_sdk.Anthropic"), \
             patch("providers.anthropic_provider.get_settings") as mock_gs, \
             patch("copilot.secrets_manager.audit_secret_used") as mock_audit:
            s = MagicMock()
            s.anthropic_api_key = "sk-ant-key"
            s.anthropic_analysis_model = "claude-haiku-4-5-20251001"
            mock_gs.return_value = s

            provider = AnthropicProvider()
            provider._get_client()
            provider._get_client()  # second call — client already initialised
        assert mock_audit.call_count == 1


# ---------------------------------------------------------------------------
# TestSettingsEndpointExpanded
# ---------------------------------------------------------------------------

class TestSettingsEndpointExpanded:
    def _mock_settings(self, webhook_secret):
        s = MagicMock()
        s.jenkins_url = "http://jenkins:8080"
        s.jenkins_user = "admin"
        s.jenkins_token = "tok"
        s.llm_provider = "anthropic"
        s.webhook_secret = webhook_secret
        return s

    def test_webhook_secret_set_true(self, client):
        with patch("config.settings._settings", self._mock_settings("mysecret")):
            r = client.get("/api/settings")
        assert r.status_code == 200
        assert r.json()["webhook_secret_set"] is True

    def test_webhook_secret_set_false(self, client):
        with patch("config.settings._settings", self._mock_settings("")):
            r = client.get("/api/settings")
        assert r.status_code == 200
        assert r.json()["webhook_secret_set"] is False

    def test_secret_value_not_exposed(self, client):
        secret_value = "super_secret_value_xyz"
        with patch("config.settings._settings", self._mock_settings(secret_value)):
            r = client.get("/api/settings")
        assert secret_value not in r.text


# ---------------------------------------------------------------------------
# TestPipelineFixesScrubbing
# ---------------------------------------------------------------------------

class TestPipelineFixesScrubbing:
    def test_retry_error_detail_scrubbed(self):
        from agent.pipeline_fixes import retry_pipeline
        token = "11cd58e68141b56335db245374772fc1"
        import jenkins as jenkins_lib
        with patch("agent.pipeline_fixes._get_jenkins_server") as mock_server, \
             patch("agent.pipeline_fixes.audit_secret_used"):
            srv = MagicMock()
            srv.build_job.side_effect = jenkins_lib.JenkinsException(
                f"HTTP 401 Unauthorized — token {token} is invalid"
            )
            mock_server.return_value = srv
            result = retry_pipeline("my-job", "42")
        assert result.success is False
        assert token not in result.detail
        assert "[REDACTED" in result.detail

    def test_configure_credential_error_scrubbed(self):
        from agent.pipeline_fixes import configure_credential
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Authorization: Basic YWRtaW46cGFzc3dvcmQ=")
        with patch("agent.pipeline_fixes._get_jenkins_server"), \
             patch("agent.pipeline_fixes.audit_secret_used"), \
             patch("requests.Session", return_value=mock_session):
            result = configure_credential("my-job", "1", credential_id="MY_CRED")
        assert result.success is False
        assert "YWRtaW46cGFzc3dvcmQ=" not in result.detail
        assert "[REDACTED" in result.detail
