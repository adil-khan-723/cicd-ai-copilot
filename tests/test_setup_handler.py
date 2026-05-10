import pytest
from pathlib import Path
from unittest.mock import patch

from ui.setup_handler import validate_setup_payload, save_credentials, save_llm_config, SetupError


def test_valid_payload_passes():
    payload = {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "abc123",
    }
    validate_setup_payload(payload)  # should not raise


def test_invalid_jenkins_url_raises():
    with pytest.raises(SetupError, match="jenkins_url"):
        validate_setup_payload({
            "jenkins_url": "not-a-url",
            "jenkins_user": "admin",
            "jenkins_token": "abc",
        })


def test_missing_field_raises():
    with pytest.raises(SetupError, match="jenkins_user"):
        validate_setup_payload({
            "jenkins_url": "http://localhost:8080",
            "jenkins_user": "",
            "jenkins_token": "abc",
        })


def test_missing_token_raises():
    with pytest.raises(SetupError, match="jenkins_token"):
        validate_setup_payload({
            "jenkins_url": "http://localhost:8080",
            "jenkins_user": "admin",
            "jenkins_token": "",
        })


@pytest.mark.parametrize("missing_field", ["jenkins_url", "jenkins_user", "jenkins_token"])
def test_missing_required_field_raises(missing_field):
    payload = {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "abc123",
    }
    del payload[missing_field]
    with pytest.raises(SetupError) as exc:
        validate_setup_payload(payload)
    assert missing_field in str(exc.value)


@pytest.mark.parametrize("empty_field", ["jenkins_url", "jenkins_user", "jenkins_token"])
def test_whitespace_only_field_raises(empty_field):
    payload = {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "abc123",
    }
    payload[empty_field] = "   "
    with pytest.raises(SetupError):
        validate_setup_payload(payload)


def test_ftp_url_raises():
    with pytest.raises(SetupError):
        validate_setup_payload({
            "jenkins_url": "ftp://jenkins:8080",
            "jenkins_user": "admin",
            "jenkins_token": "tok",
        })


def test_https_url_passes():
    validate_setup_payload({
        "jenkins_url": "https://jenkins.example.com",
        "jenkins_user": "admin",
        "jenkins_token": "tok",
    })


# ── save_credentials / _write_env ─────────────────────────────────────────────

def _save(tmp_path, payload):
    """Helper: call save_credentials with env file redirected to tmp_path."""
    env_file = tmp_path / ".env"
    with patch("ui.setup_handler._ENV_PATH", env_file):
        save_credentials(payload)
    return env_file


def test_save_credentials_creates_env_file(tmp_path):
    f = _save(tmp_path, {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "tok123",
    })
    assert f.exists()
    content = f.read_text()
    assert "JENKINS_URL=http://localhost:8080" in content
    assert "JENKINS_USER=admin" in content
    assert "JENKINS_TOKEN=tok123" in content


def test_save_credentials_updates_existing_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("JENKINS_URL=http://old:8080\nOTHER_KEY=keep\n")
    with patch("ui.setup_handler._ENV_PATH", env_file):
        save_credentials({
            "jenkins_url": "http://new:8080",
            "jenkins_user": "admin",
            "jenkins_token": "tok",
        })
    content = env_file.read_text()
    assert "http://new:8080" in content
    assert "http://old:8080" not in content
    assert "OTHER_KEY=keep" in content


def test_save_credentials_preserves_unrelated_keys(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=sk-abc\nGITHUB_TOKEN=ghp_xyz\n")
    with patch("ui.setup_handler._ENV_PATH", env_file):
        save_credentials({
            "jenkins_url": "http://localhost:8080",
            "jenkins_user": "admin",
            "jenkins_token": "tok",
        })
    content = env_file.read_text()
    assert "ANTHROPIC_API_KEY=sk-abc" in content
    assert "GITHUB_TOKEN=ghp_xyz" in content


def test_save_credentials_resets_settings_cache(tmp_path):
    env_file = tmp_path / ".env"
    import config.settings as cfg_module
    original = cfg_module._settings
    try:
        cfg_module._settings = "stale"
        with patch("ui.setup_handler._ENV_PATH", env_file):
            save_credentials({
                "jenkins_url": "http://localhost:8080",
                "jenkins_user": "admin",
                "jenkins_token": "tok",
            })
        assert cfg_module._settings is None
    finally:
        cfg_module._settings = original


def test_save_credentials_raises_on_invalid_payload():
    with pytest.raises(SetupError):
        save_credentials({"jenkins_url": "", "jenkins_user": "admin", "jenkins_token": "tok"})


def test_save_credentials_persists_auth_method_token(tmp_path):
    f = _save(tmp_path, {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "tok",
        "jenkins_auth_method": "token",
    })
    assert "JENKINS_AUTH_METHOD=token" in f.read_text()


def test_save_credentials_persists_auth_method_password(tmp_path):
    f = _save(tmp_path, {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "admin123",
        "jenkins_auth_method": "password",
    })
    assert "JENKINS_AUTH_METHOD=password" in f.read_text()


def test_save_credentials_defaults_auth_method_to_token(tmp_path):
    f = _save(tmp_path, {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "tok",
    })
    assert "JENKINS_AUTH_METHOD=token" in f.read_text()


def test_save_credentials_rejects_invalid_auth_method_falls_back_to_token(tmp_path):
    f = _save(tmp_path, {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "tok",
        "jenkins_auth_method": "ldap",
    })
    assert "JENKINS_AUTH_METHOD=token" in f.read_text()


def test_save_credentials_strips_whitespace_from_user_and_token(tmp_path):
    # URL must be valid (no leading space), but user/token trailing spaces are stripped
    f = _save(tmp_path, {
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "  admin  ",
        "jenkins_token": "  tok  ",
    })
    content = f.read_text()
    assert "JENKINS_USER=admin" in content
    assert "JENKINS_TOKEN=tok" in content


# ── LLM config tests ─────────────────────────────────────────────────────────

def _save_llm(tmp_path, payload):
    env = tmp_path / ".env"
    with patch("ui.setup_handler._ENV_PATH", env), \
         patch("config.settings._settings", None):
        save_llm_config(payload)
    return env


def test_save_llm_config_writes_anthropic_key(tmp_path):
    f = _save_llm(tmp_path, {
        "provider": "anthropic",
        "anthropic_api_key": "sk-ant-test123",
        "anthropic_analysis_model": "claude-haiku-4-5-20251001",
    })
    content = f.read_text()
    assert "LLM_PROVIDER=anthropic" in content
    assert "ANTHROPIC_API_KEY=sk-ant-test123" in content
    assert "ANTHROPIC_ANALYSIS_MODEL=claude-haiku-4-5-20251001" in content


def test_save_llm_config_skips_blank_key_preserves_existing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-ant-existing\nLLM_PROVIDER=ollama\n")
    with patch("ui.setup_handler._ENV_PATH", env), \
         patch("config.settings._settings", None):
        save_llm_config({"provider": "anthropic", "anthropic_api_key": ""})
    content = env.read_text()
    # Provider switched but existing key preserved (no blank overwrite)
    assert "LLM_PROVIDER=anthropic" in content
    assert "ANTHROPIC_API_KEY=sk-ant-existing" in content


def test_save_llm_config_rejects_bad_key_format(tmp_path):
    env = tmp_path / ".env"
    with patch("ui.setup_handler._ENV_PATH", env):
        with pytest.raises(SetupError):
            save_llm_config({"provider": "anthropic", "anthropic_api_key": "not-a-real-key"})


def test_save_llm_config_rejects_unknown_provider(tmp_path):
    env = tmp_path / ".env"
    with patch("ui.setup_handler._ENV_PATH", env):
        with pytest.raises(SetupError):
            save_llm_config({"provider": "openai"})


def test_save_llm_config_writes_ollama_settings(tmp_path):
    f = _save_llm(tmp_path, {
        "provider": "ollama",
        "ollama_base_url": "http://192.168.1.5:11434",
        "analysis_model": "llama3.1:8b",
    })
    content = f.read_text()
    assert "LLM_PROVIDER=ollama" in content
    assert "OLLAMA_BASE_URL=http://192.168.1.5:11434" in content
    assert "ANALYSIS_MODEL=llama3.1:8b" in content


def test_save_llm_config_clears_settings_cache(tmp_path):
    env = tmp_path / ".env"
    import config.settings as cfg_module
    original = cfg_module._settings
    cfg_module._settings = "fake-cached-instance"
    try:
        with patch("ui.setup_handler._ENV_PATH", env):
            save_llm_config({"provider": "ollama"})
        assert cfg_module._settings is None
    finally:
        cfg_module._settings = original
