"""
Tests for webhook/validators.py — HMAC signature validation.
"""
import hashlib
import hmac
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from webhook.validators import validate_jenkins_webhook, validate_github_webhook


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jenkins_sig(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _github_sig(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _make_request(headers: dict, body: bytes):
    """Minimal async mock of a FastAPI Request."""
    req = AsyncMock()
    req.headers = headers
    req.body = AsyncMock(return_value=body)
    return req


# ── validate_jenkins_webhook ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jenkins_no_secret_skips_validation():
    """Empty secret → no validation, no exception."""
    req = _make_request({}, b'{"name":"job","build":{}}')
    await validate_jenkins_webhook(req, secret="")


@pytest.mark.asyncio
async def test_jenkins_valid_signature_passes():
    secret = "mysecret"
    body = b'{"name":"job","build":{"number":1}}'
    sig = _jenkins_sig(body, secret)
    req = _make_request({"X-Jenkins-Signature": sig}, body)
    await validate_jenkins_webhook(req, secret=secret)


@pytest.mark.asyncio
async def test_jenkins_invalid_signature_raises_401():
    req = _make_request({"X-Jenkins-Signature": "sha256=badhash"}, b'body')
    with pytest.raises(HTTPException) as exc:
        await validate_jenkins_webhook(req, secret="mysecret")
    assert exc.value.status_code == 401
    assert "Invalid" in exc.value.detail


@pytest.mark.asyncio
async def test_jenkins_missing_signature_header_raises_401():
    req = _make_request({}, b'body')
    with pytest.raises(HTTPException) as exc:
        await validate_jenkins_webhook(req, secret="mysecret")
    assert exc.value.status_code == 401
    assert "Missing" in exc.value.detail


@pytest.mark.asyncio
async def test_jenkins_wrong_body_raises_401():
    secret = "mysecret"
    body = b'{"name":"job"}'
    sig = _jenkins_sig(body, secret)
    req = _make_request({"X-Jenkins-Signature": sig}, b'tampered body')
    with pytest.raises(HTTPException) as exc:
        await validate_jenkins_webhook(req, secret=secret)
    assert exc.value.status_code == 401


# ── validate_github_webhook ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_github_no_secret_skips_validation():
    req = _make_request({}, b'{}')
    await validate_github_webhook(req, secret="")


@pytest.mark.asyncio
async def test_github_valid_signature_passes():
    secret = "gh-secret"
    body = b'{"action":"completed"}'
    sig = _github_sig(body, secret)
    req = _make_request({"X-Hub-Signature-256": sig}, body)
    await validate_github_webhook(req, secret=secret)


@pytest.mark.asyncio
async def test_github_invalid_signature_raises_401():
    req = _make_request({"X-Hub-Signature-256": "sha256=badhash"}, b'body')
    with pytest.raises(HTTPException) as exc:
        await validate_github_webhook(req, secret="gh-secret")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_github_missing_signature_header_raises_401():
    req = _make_request({}, b'body')
    with pytest.raises(HTTPException) as exc:
        await validate_github_webhook(req, secret="gh-secret")
    assert exc.value.status_code == 401
    assert "Missing" in exc.value.detail


@pytest.mark.asyncio
async def test_github_wrong_body_raises_401():
    secret = "gh-secret"
    body = b'{"action":"completed"}'
    sig = _github_sig(body, secret)
    req = _make_request({"X-Hub-Signature-256": sig}, b'tampered')
    with pytest.raises(HTTPException) as exc:
        await validate_github_webhook(req, secret=secret)
    assert exc.value.status_code == 401
