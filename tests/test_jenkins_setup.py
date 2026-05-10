"""Unit tests for ui.jenkins_setup — auto-configure Jenkins for webhooks."""
import pytest
from unittest.mock import patch, MagicMock
from ui.jenkins_setup import (
    configure_jenkins_for_webhooks,
    _inject_notification_property,
    NOTIFICATION_PROPERTY_TAG,
)


def test_inject_into_empty_properties():
    config = '<flow-definition><properties/></flow-definition>'
    out = _inject_notification_property(config, "http://app:8000/webhook/jenkins-notification")
    assert "<properties>" in out
    assert "</properties>" in out
    assert NOTIFICATION_PROPERTY_TAG in out
    assert "<event>all</event>" in out
    assert "<branch>.*</branch>" in out
    assert "http://app:8000/webhook/jenkins-notification" in out


def test_inject_into_existing_properties():
    config = '<flow-definition><properties><other-prop/></properties></flow-definition>'
    out = _inject_notification_property(config, "http://app:8000/webhook/jenkins-notification")
    assert "<other-prop/>" in out  # preserved
    assert NOTIFICATION_PROPERTY_TAG in out


def test_inject_idempotent_replaces_old_endpoint():
    """Re-running with a different URL should replace, not duplicate."""
    config = (
        '<flow-definition><properties>'
        f'<{NOTIFICATION_PROPERTY_TAG} plugin="notification">'
        '<endpoints><com.tikal.hudson.plugins.notification.Endpoint>'
        '<url>http://OLD:8000/webhook/jenkins-notification</url>'
        '</com.tikal.hudson.plugins.notification.Endpoint></endpoints>'
        f'</{NOTIFICATION_PROPERTY_TAG}>'
        '</properties></flow-definition>'
    )
    out = _inject_notification_property(config, "http://NEW:8000/webhook/jenkins-notification")
    assert "OLD" not in out
    assert "NEW" in out
    # Only one notification property block
    assert out.count(f"<{NOTIFICATION_PROPERTY_TAG} ") == 1


# ── End-to-end (mocked HTTP) ───────────────────────────────────────────────

class _FakeResp:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or ""
    def json(self):
        return self._body
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_full_flow_installs_missing_plugins_and_configures_jobs():
    crumb_resp = _FakeResp(200, {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc123"})
    plugins_resp = _FakeResp(200, {"plugins": [{"shortName": "git", "active": True}]})  # no notification, no junit
    jobs_resp = _FakeResp(200, {"jobs": [{"name": "job-a"}, {"name": "job-b"}]})
    job_a_config = _FakeResp(200, text='<flow-definition><properties/></flow-definition>')
    job_b_config = _FakeResp(200, text='<flow-definition><properties/></flow-definition>')

    def fake_get(url, **kw):
        if "/crumbIssuer" in url: return crumb_resp
        if "/pluginManager/api/json" in url: return plugins_resp
        if url.endswith("/api/json"): return jobs_resp
        if "job/job-a/config.xml" in url: return job_a_config
        if "job/job-b/config.xml" in url: return job_b_config
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url, **kw):
        if "/scriptText" in url:
            return _FakeResp(200, text="installed: " + kw.get("data", {}).get("script", "").split('"')[1])
        if "config.xml" in url:
            return _FakeResp(200)
        raise AssertionError(f"unexpected POST {url}")

    sess_get = MagicMock(return_value=crumb_resp)
    sess_get.return_value.cookies = {"COOKIE": "v"}
    with patch("requests.Session") as Sess, \
         patch("requests.get", side_effect=fake_get), \
         patch("requests.post", side_effect=fake_post):
        Sess.return_value.get.return_value = crumb_resp
        Sess.return_value.cookies = {}
        report = configure_jenkins_for_webhooks(
            "http://jenkins:8080", "admin", "tok",
            "http://app:8000/webhook/jenkins-notification",
        )

    assert report.ok
    assert "notification" in report.plugins_installed
    assert "junit" in report.plugins_installed
    assert report.restart_required is True
    assert sorted(report.jobs_configured) == ["job-a", "job-b"]


def test_skips_already_installed_plugins():
    crumb_resp = _FakeResp(200, {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc"})
    plugins_resp = _FakeResp(200, {"plugins": [
        {"shortName": "notification", "active": True},
        {"shortName": "junit", "active": True},
    ]})
    jobs_resp = _FakeResp(200, {"jobs": []})

    def fake_get(url, **kw):
        if "/crumbIssuer" in url: return crumb_resp
        if "/pluginManager/api/json" in url: return plugins_resp
        if url.endswith("/api/json"): return jobs_resp
        raise AssertionError(f"unexpected GET {url}")

    with patch("requests.Session") as Sess, \
         patch("requests.get", side_effect=fake_get), \
         patch("requests.post", side_effect=AssertionError("should not POST")):
        Sess.return_value.get.return_value = crumb_resp
        Sess.return_value.cookies = {}
        report = configure_jenkins_for_webhooks(
            "http://jenkins:8080", "admin", "tok",
            "http://app:8000/webhook/jenkins-notification",
        )
    assert report.plugins_installed == []
    assert sorted(report.plugins_already_present) == ["junit", "notification"]
    assert report.restart_required is False


def test_idempotent_skips_already_configured_jobs():
    """Job whose config already has our exact webhook URL should be skipped."""
    crumb_resp = _FakeResp(200, {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc"})
    plugins_resp = _FakeResp(200, {"plugins": [
        {"shortName": "notification", "active": True},
        {"shortName": "junit", "active": True},
    ]})
    jobs_resp = _FakeResp(200, {"jobs": [{"name": "configured"}, {"name": "fresh"}]})
    webhook_url = "http://app:8000/webhook/jenkins-notification"
    configured_xml = (
        f'<flow-definition><properties>'
        f'<{NOTIFICATION_PROPERTY_TAG} plugin="notification">'
        f'<endpoints><com.tikal.hudson.plugins.notification.Endpoint>'
        f'<url>{webhook_url}</url>'
        f'</com.tikal.hudson.plugins.notification.Endpoint></endpoints>'
        f'</{NOTIFICATION_PROPERTY_TAG}>'
        f'</properties></flow-definition>'
    )
    fresh_xml = '<flow-definition><properties/></flow-definition>'

    def fake_get(url, **kw):
        if "/crumbIssuer" in url: return crumb_resp
        if "/pluginManager/api/json" in url: return plugins_resp
        if url.endswith("/api/json"): return jobs_resp
        if "job/configured/config.xml" in url: return _FakeResp(200, text=configured_xml)
        if "job/fresh/config.xml" in url: return _FakeResp(200, text=fresh_xml)
        raise AssertionError(f"unexpected GET {url}")

    posts = []
    def fake_post(url, **kw):
        posts.append(url)
        return _FakeResp(200)

    with patch("requests.Session") as Sess, \
         patch("requests.get", side_effect=fake_get), \
         patch("requests.post", side_effect=fake_post):
        Sess.return_value.get.return_value = crumb_resp
        Sess.return_value.cookies = {}
        report = configure_jenkins_for_webhooks(
            "http://jenkins:8080", "admin", "tok", webhook_url,
        )
    assert report.jobs_configured == ["fresh"]
    assert report.jobs_already_configured == ["configured"]
    # Only one POST (to fresh's config.xml, not configured's)
    assert len([p for p in posts if "config.xml" in p]) == 1


def test_csrf_disabled_returns_no_crumb():
    """Jenkins with CSRF disabled returns 404 on /crumbIssuer — should not abort."""
    crumb_404 = _FakeResp(404, {})
    plugins_resp = _FakeResp(200, {"plugins": [
        {"shortName": "notification", "active": True},
        {"shortName": "junit", "active": True},
    ]})
    jobs_resp = _FakeResp(200, {"jobs": []})

    def fake_get(url, **kw):
        if "/pluginManager/api/json" in url: return plugins_resp
        if url.endswith("/api/json"): return jobs_resp
        raise AssertionError(f"unexpected GET {url}")

    with patch("requests.Session") as Sess, \
         patch("requests.get", side_effect=fake_get), \
         patch("requests.post"):
        Sess.return_value.get.return_value = crumb_404
        Sess.return_value.cookies = {}
        report = configure_jenkins_for_webhooks(
            "http://jenkins:8080", "admin", "tok",
            "http://app:8000/webhook/jenkins-notification",
        )
    assert report.ok
    assert report.errors == []
