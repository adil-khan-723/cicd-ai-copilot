"""Tests for the Jenkins failure poller (fallback when Notification Plugin fails)."""
import asyncio
import pytest
from unittest.mock import patch, MagicMock


class _FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
    def json(self):
        return self._body


@pytest.mark.asyncio
async def test_poller_primes_on_first_scan_no_processing():
    """First scan must NOT re-analyze existing builds — only seeds the seen set."""
    from ui import routes
    captured: list = []
    body = {"jobs": [
        {"name": "job-a", "lastCompletedBuild": {"number": 5, "result": "FAILURE"}},
        {"name": "job-b", "lastCompletedBuild": {"number": 12, "result": "SUCCESS"}},
    ]}
    with patch("requests.get", return_value=_FakeResp(200, body)), \
         patch("config.get_settings") as gs, \
         patch("webhook.server._process_notification_failure_sync",
               side_effect=lambda j, b, p: captured.append((j, b))), \
         patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        gs.return_value.jenkins_url = "http://j:8080"
        gs.return_value.jenkins_token = "tok"
        gs.return_value.jenkins_user = "admin"
        with pytest.raises(asyncio.CancelledError):
            await routes._jenkins_failure_poller()
    assert captured == [], "First scan should prime, not process"


@pytest.mark.asyncio
async def test_poller_detects_new_failure_after_priming():
    """After priming, a newly-appearing failure must trigger _process_notification_failure_sync."""
    from ui import routes
    captured: list = []
    scan_count = {"n": 0}
    body_round_1 = {"jobs": [
        {"name": "job-a", "lastCompletedBuild": {"number": 5, "result": "SUCCESS"}},
    ]}
    body_round_2 = {"jobs": [
        {"name": "job-a", "lastCompletedBuild": {"number": 6, "result": "FAILURE"}},
    ]}

    def fake_get(*args, **kwargs):
        scan_count["n"] += 1
        return _FakeResp(200, body_round_1 if scan_count["n"] == 1 else body_round_2)

    async def fake_sleep(_):
        if scan_count["n"] >= 2:
            raise asyncio.CancelledError

    with patch("requests.get", side_effect=fake_get), \
         patch("config.get_settings") as gs, \
         patch("webhook.server._process_notification_failure_sync",
               side_effect=lambda j, b, p: captured.append((j, b))), \
         patch("asyncio.sleep", side_effect=fake_sleep):
        gs.return_value.jenkins_url = "http://j:8080"
        gs.return_value.jenkins_token = "tok"
        gs.return_value.jenkins_user = "admin"
        with pytest.raises(asyncio.CancelledError):
            await routes._jenkins_failure_poller()
    assert ("job-a", "6") in captured


@pytest.mark.asyncio
async def test_poller_dedup_does_not_reanalyze_same_build():
    """Same (job, build) seen twice should only be processed once."""
    from ui import routes
    captured: list = []
    scan_count = {"n": 0}
    # Both rounds return the SAME failure — should only fire once after priming
    body = {"jobs": [
        {"name": "job-a", "lastCompletedBuild": {"number": 5, "result": "SUCCESS"}},  # priming
    ]}
    body_with_fail = {"jobs": [
        {"name": "job-a", "lastCompletedBuild": {"number": 6, "result": "FAILURE"}},
    ]}

    def fake_get(*args, **kwargs):
        scan_count["n"] += 1
        if scan_count["n"] == 1:
            return _FakeResp(200, body)
        return _FakeResp(200, body_with_fail)

    async def fake_sleep(_):
        if scan_count["n"] >= 4:  # 4 scans: prime + 3 with same failure
            raise asyncio.CancelledError

    with patch("requests.get", side_effect=fake_get), \
         patch("config.get_settings") as gs, \
         patch("webhook.server._process_notification_failure_sync",
               side_effect=lambda j, b, p: captured.append((j, b))), \
         patch("asyncio.sleep", side_effect=fake_sleep):
        gs.return_value.jenkins_url = "http://j:8080"
        gs.return_value.jenkins_token = "tok"
        gs.return_value.jenkins_user = "admin"
        with pytest.raises(asyncio.CancelledError):
            await routes._jenkins_failure_poller()
    # Failure for build 6 fires exactly once across multiple scans
    assert captured.count(("job-a", "6")) == 1


@pytest.mark.asyncio
async def test_poller_no_jenkins_config_exits_quietly():
    """When Jenkins not configured, poller should not crash — just no-op."""
    from ui import routes
    scan_count = {"n": 0}

    async def fake_sleep(_):
        scan_count["n"] += 1
        if scan_count["n"] >= 2:
            raise asyncio.CancelledError

    with patch("requests.get", side_effect=AssertionError("should not be called")), \
         patch("config.get_settings") as gs, \
         patch("asyncio.sleep", side_effect=fake_sleep):
        gs.return_value.jenkins_url = ""
        gs.return_value.jenkins_token = ""
        gs.return_value.jenkins_user = ""
        with pytest.raises(asyncio.CancelledError):
            await routes._jenkins_failure_poller()
    assert scan_count["n"] >= 2
