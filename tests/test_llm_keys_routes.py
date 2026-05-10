"""HTTP-level tests for /api/llm-keys/* routes."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import ui.llm_keys_store as ks
    importlib.reload(ks)
    yield tmp_path


@pytest.fixture
def client():
    from webhook.server import app
    return TestClient(app, raise_server_exceptions=False)


def test_list_keys_empty(client):
    r = client.get("/api/llm-keys")
    assert r.status_code == 200
    assert r.json() == {"keys": []}


def test_create_key_success(client):
    with patch("ui.llm_keys_store._write_env_for_provider"):
        r = client.post("/api/llm-keys", json={
            "name": "work", "provider": "anthropic", "key": "sk-ant-test123"
        })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["key"]["name"] == "work"
    assert body["key"]["active"] is True  # first key auto-activates
    assert "key" not in body["key"]  # masked


def test_create_key_invalid_provider(client):
    r = client.post("/api/llm-keys", json={
        "name": "x", "provider": "openai", "key": "sk-foo"
    })
    assert r.status_code == 422


def test_create_key_bad_format(client):
    r = client.post("/api/llm-keys", json={
        "name": "x", "provider": "anthropic", "key": "wrong"
    })
    assert r.status_code == 422


def test_activate_unknown_returns_404(client):
    r = client.post("/api/llm-keys/nope/activate")
    assert r.status_code == 404


def test_delete_active_returns_409(client):
    with patch("ui.llm_keys_store._write_env_for_provider"):
        created = client.post("/api/llm-keys", json={
            "name": "a", "provider": "anthropic", "key": "sk-ant-aaa"
        }).json()
    r = client.delete(f"/api/llm-keys/{created['key']['id']}")
    assert r.status_code == 409
    assert "active" in r.json()["detail"].lower()


def test_full_lifecycle_create_activate_delete(client):
    with patch("ui.llm_keys_store._write_env_for_provider"):
        k1 = client.post("/api/llm-keys", json={
            "name": "old", "provider": "anthropic", "key": "sk-ant-aaa"
        }).json()["key"]
        k2 = client.post("/api/llm-keys", json={
            "name": "new", "provider": "anthropic", "key": "sk-ant-bbb"
        }).json()["key"]
        # Activate the second one
        r = client.post(f"/api/llm-keys/{k2['id']}/activate")
        assert r.status_code == 200
        # Now delete the first (no longer active)
        r = client.delete(f"/api/llm-keys/{k1['id']}")
        assert r.status_code == 200
    keys = client.get("/api/llm-keys").json()["keys"]
    assert len(keys) == 1
    assert keys[0]["name"] == "new"
