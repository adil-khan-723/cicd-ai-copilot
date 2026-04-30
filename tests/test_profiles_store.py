"""
Tests for ui/profiles_store.py — profile CRUD, activation, masking, persistence.
Uses a temp DATA_DIR so tests never touch ~/.devops-ai.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Each test gets its own DATA_DIR — no shared state."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Reset module-level caches if any
    import importlib
    import ui.profiles_store as ps
    importlib.reload(ps)
    yield tmp_path


def _store():
    from ui import profiles_store
    return profiles_store


# ── list_profiles / add_profile ───────────────────────────────────────────────

def test_list_profiles_empty_on_fresh_dir():
    assert _store().list_profiles() == []


def test_add_profile_returns_masked():
    profile = _store().add_profile(
        alias="dev",
        jenkins_url="http://jenkins:8080",
        jenkins_user="admin",
        jenkins_token="secret123",
    )
    assert profile["alias"] == "dev"
    assert profile["jenkins_url"] == "http://jenkins:8080"
    assert "jenkins_token" not in profile


def test_add_profile_appears_in_list():
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    profiles = _store().list_profiles()
    assert len(profiles) == 1
    assert profiles[0]["alias"] == "dev"


def test_add_profile_first_is_auto_active():
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    profiles = _store().list_profiles()
    assert profiles[0]["active"] is True


def test_add_second_profile_not_auto_active():
    _store().add_profile("dev",  "http://j:8080", "admin", "tok1")
    _store().add_profile("prod", "http://j:9090", "admin", "tok2")
    profiles = _store().list_profiles()
    active = [p for p in profiles if p["active"]]
    assert len(active) == 1
    assert active[0]["alias"] == "dev"


def test_add_profile_trailing_slash_stripped():
    _store().add_profile("dev", "http://j:8080/", "admin", "tok")
    profiles = _store().list_profiles()
    assert profiles[0]["jenkins_url"] == "http://j:8080"


def test_profiles_persisted_to_disk(tmp_path):
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    path = tmp_path / "profiles.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) == 1
    assert data[0]["jenkins_token"] == "tok"  # stored unmasked on disk


# ── token masking ─────────────────────────────────────────────────────────────

def test_token_never_returned_via_list():
    _store().add_profile("dev", "http://j:8080", "admin", "supersecret")
    for p in _store().list_profiles():
        assert "jenkins_token" not in p


def test_get_active_profile_returns_token():
    _store().add_profile("dev", "http://j:8080", "admin", "supersecret")
    active = _store().get_active_profile()
    assert active is not None
    assert active["jenkins_token"] == "supersecret"


# ── activate_profile ──────────────────────────────────────────────────────────

def test_activate_profile_switches_active():
    _store().add_profile("dev",  "http://j:8080", "admin", "tok1")
    _store().add_profile("prod", "http://j:9090", "admin", "tok2")
    profiles = _store().list_profiles()
    prod_id = next(p["id"] for p in profiles if p["alias"] == "prod")

    with patch("ui.setup_handler.save_credentials"), \
         patch("ui.event_bus.bus.clear_history"), \
         patch("analyzer.cache.clear"):
        result = _store().activate_profile(prod_id)

    assert result is True
    active = _store().get_active_profile()
    assert active["alias"] == "prod"


def test_activate_profile_calls_save_credentials():
    _store().add_profile("dev", "http://j:8080", "admin", "tok1")
    _store().add_profile("prod", "http://j:9090", "admin", "tok2")
    profiles = _store().list_profiles()
    prod_id = next(p["id"] for p in profiles if p["alias"] == "prod")

    with patch("ui.setup_handler.save_credentials") as mock_save, \
         patch("ui.event_bus.bus.clear_history"), \
         patch("analyzer.cache.clear"):
        _store().activate_profile(prod_id)

    mock_save.assert_called_once()
    call_kwargs = mock_save.call_args[0][0]
    assert call_kwargs["jenkins_url"] == "http://j:9090"


def test_activate_nonexistent_profile_returns_false():
    result = _store().activate_profile("nonexistent-id")
    assert result is False


def test_activate_clears_event_bus_history():
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    profiles = _store().list_profiles()
    pid = profiles[0]["id"]

    with patch("ui.setup_handler.save_credentials"), \
         patch("ui.event_bus.bus.clear_history") as mock_clear, \
         patch("analyzer.cache.clear"):
        _store().activate_profile(pid)

    mock_clear.assert_called_once()


def test_activate_clears_analysis_cache():
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    profiles = _store().list_profiles()
    pid = profiles[0]["id"]

    with patch("ui.setup_handler.save_credentials"), \
         patch("ui.event_bus.bus.clear_history"), \
         patch("analyzer.cache.clear") as mock_clear:
        _store().activate_profile(pid)

    mock_clear.assert_called_once()


# ── delete_profile ────────────────────────────────────────────────────────────

def test_delete_profile_removes_it():
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    pid = _store().list_profiles()[0]["id"]
    result = _store().delete_profile(pid)
    assert result is True
    assert _store().list_profiles() == []


def test_delete_nonexistent_profile_returns_false():
    result = _store().delete_profile("does-not-exist")
    assert result is False


def test_delete_active_profile_activates_next():
    _store().add_profile("dev",  "http://j:8080", "admin", "tok1")
    _store().add_profile("prod", "http://j:9090", "admin", "tok2")
    profiles = _store().list_profiles()
    dev_id = next(p["id"] for p in profiles if p["alias"] == "dev")

    _store().delete_profile(dev_id)

    remaining = _store().list_profiles()
    assert len(remaining) == 1
    assert remaining[0]["active"] is True
    assert remaining[0]["alias"] == "prod"


# ── update_profile ────────────────────────────────────────────────────────────

def test_update_profile_renames_alias():
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    pid = _store().list_profiles()[0]["id"]
    result = _store().update_profile(pid, "development")
    assert result is True
    assert _store().list_profiles()[0]["alias"] == "development"


def test_update_nonexistent_profile_returns_false():
    result = _store().update_profile("fake-id", "new-alias")
    assert result is False


# ── get_active_profile_dir ────────────────────────────────────────────────────

def test_get_active_profile_dir_returns_path(tmp_path):
    _store().add_profile("dev", "http://j:8080", "admin", "tok")
    d = _store().get_active_profile_dir()
    assert d.is_dir()


def test_get_active_profile_dir_fallback_when_no_profiles(tmp_path):
    d = _store().get_active_profile_dir()
    assert d == tmp_path
