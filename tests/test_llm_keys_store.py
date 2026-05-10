"""
Tests for ui/llm_keys_store.py — LLM API key CRUD, activation, masking, .env wiring.
Uses a temp DATA_DIR so tests never touch ~/.devops-ai.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import ui.llm_keys_store as ks
    importlib.reload(ks)
    yield tmp_path


def _store():
    from ui import llm_keys_store
    return llm_keys_store


# ── add_key ────────────────────────────────────────────────────────────────────

def test_add_key_returns_masked():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        k = _store().add_key("work", "anthropic", "sk-ant-secret123abc")
    assert k["name"] == "work"
    assert k["provider"] == "anthropic"
    assert "key" not in k
    assert k["key_preview"].startswith("sk-ant-")
    assert "secret" not in k["key_preview"]


def test_first_key_for_provider_auto_activates():
    with patch("ui.llm_keys_store._write_env_for_provider") as wenv:
        k = _store().add_key("first", "anthropic", "sk-ant-aaaa")
        assert k["active"] is True
        wenv.assert_called_once_with("anthropic", "sk-ant-aaaa")


def test_second_key_does_not_auto_activate():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        _store().add_key("first", "anthropic", "sk-ant-aaaa")
        k2 = _store().add_key("second", "anthropic", "sk-ant-bbbb")
    assert k2["active"] is False


def test_duplicate_name_within_provider_raises():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        _store().add_key("work", "anthropic", "sk-ant-aaaa")
        with pytest.raises(ValueError, match="already exists"):
            _store().add_key("work", "anthropic", "sk-ant-bbbb")


def test_invalid_provider_raises():
    with pytest.raises(ValueError, match="provider"):
        _store().add_key("x", "openai", "sk-foo")


def test_anthropic_key_must_start_with_sk():
    with pytest.raises(ValueError, match="sk-"):
        _store().add_key("x", "anthropic", "wrong-prefix")


def test_empty_name_raises():
    with pytest.raises(ValueError, match="name"):
        _store().add_key("  ", "anthropic", "sk-ant-aaa")


# ── list_keys ──────────────────────────────────────────────────────────────────

def test_list_keys_empty_initially():
    assert _store().list_keys() == []


def test_list_keys_masks_secret():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        _store().add_key("work", "anthropic", "sk-ant-secret-abc-1234")
    keys = _store().list_keys()
    assert len(keys) == 1
    assert "key" not in keys[0]
    assert "secret" not in keys[0]["key_preview"]


def test_list_keys_sorted_by_provider_then_creation():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        _store().add_key("a", "anthropic", "sk-ant-1111")
        _store().add_key("b", "anthropic", "sk-ant-2222")
    keys = _store().list_keys()
    # Same provider — older first
    assert keys[0]["name"] == "a"
    assert keys[1]["name"] == "b"


# ── activate_key ───────────────────────────────────────────────────────────────

def test_activate_key_swaps_active_within_provider():
    with patch("ui.llm_keys_store._write_env_for_provider") as wenv:
        k1 = _store().add_key("a", "anthropic", "sk-ant-1111")
        k2 = _store().add_key("b", "anthropic", "sk-ant-2222")
        wenv.reset_mock()
        ok = _store().activate_key(k2["id"])
    assert ok is True
    keys = _store().list_keys()
    actives = [k for k in keys if k["active"]]
    assert len(actives) == 1
    assert actives[0]["name"] == "b"
    wenv.assert_called_once_with("anthropic", "sk-ant-2222")


def test_activate_unknown_key_returns_false():
    assert _store().activate_key("nonexistent-id") is False


def test_get_active_key_returns_full_secret():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        _store().add_key("work", "anthropic", "sk-ant-fullvalue")
    active = _store().get_active_key("anthropic")
    assert active is not None
    assert active["key"] == "sk-ant-fullvalue"


def test_get_active_key_none_when_no_keys():
    assert _store().get_active_key("anthropic") is None


# ── delete_key ─────────────────────────────────────────────────────────────────

def test_delete_inactive_key_succeeds():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        k1 = _store().add_key("a", "anthropic", "sk-ant-1111")  # active
        k2 = _store().add_key("b", "anthropic", "sk-ant-2222")  # inactive
    ok, err = _store().delete_key(k2["id"])
    assert ok is True
    assert err == ""
    assert len(_store().list_keys()) == 1


def test_delete_active_key_blocked():
    with patch("ui.llm_keys_store._write_env_for_provider"):
        k1 = _store().add_key("a", "anthropic", "sk-ant-1111")
    ok, err = _store().delete_key(k1["id"])
    assert ok is False
    assert "active" in err.lower()
    assert len(_store().list_keys()) == 1


def test_delete_active_after_activating_another_succeeds():
    """Workflow: activate replacement → then delete prior active."""
    with patch("ui.llm_keys_store._write_env_for_provider"):
        k1 = _store().add_key("old", "anthropic", "sk-ant-1111")
        k2 = _store().add_key("new", "anthropic", "sk-ant-2222")
        _store().activate_key(k2["id"])
        ok, err = _store().delete_key(k1["id"])
    assert ok is True
    keys = _store().list_keys()
    assert len(keys) == 1
    assert keys[0]["name"] == "new"


def test_delete_unknown_key_returns_false():
    ok, err = _store().delete_key("nope")
    assert ok is False
    assert "not found" in err.lower()


# ── persistence ────────────────────────────────────────────────────────────────

def test_keys_persisted_to_disk(tmp_path):
    with patch("ui.llm_keys_store._write_env_for_provider"):
        _store().add_key("work", "anthropic", "sk-ant-persist123")
    path = tmp_path / "llm_keys.json"
    assert path.exists()
    import json
    data = json.loads(path.read_text())
    assert len(data) == 1
    assert data[0]["key"] == "sk-ant-persist123"  # unmasked on disk
