"""
Tests for ui/jobs_handler.py — Jenkins job listing, trigger, status mapping.
"""
import pytest
from unittest.mock import patch, MagicMock
import jenkins as jenkins_lib

from ui.jobs_handler import get_jenkins_jobs, trigger_job, _color_to_status


# ── _color_to_status ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("color,expected", [
    ("blue",         "success"),
    ("blue_anime",   "success"),
    ("red",          "failure"),
    ("red_anime",    "failure"),   # red present → failure wins
    ("aborted",      "unknown"),
    ("notbuilt",     "unknown"),
    ("grey",         "unknown"),
    ("",             "unknown"),
    ("blue_running", "success"),   # blue substring
])
def test_color_to_status(color, expected):
    assert _color_to_status(color) == expected


def test_color_anime_is_running():
    # "anime" in color with no blue/red → running
    assert _color_to_status("anime") == "running"


# ── get_jenkins_jobs ──────────────────────────────────────────────────────────

def _mock_settings(url="http://jenkins:8080", user="admin", token="tok"):
    s = MagicMock()
    s.jenkins_url = url
    s.jenkins_user = user
    s.jenkins_token = token
    return s


def test_get_jenkins_jobs_returns_list():
    mock_server = MagicMock()
    mock_server.get_jobs.return_value = [
        {"name": "build-api", "url": "http://j/job/build-api/", "color": "blue"},
        {"name": "deploy",    "url": "http://j/job/deploy/",    "color": "red"},
    ]
    with patch("ui.jobs_handler.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.jobs_handler.get_settings", return_value=_mock_settings()):
        jobs = get_jenkins_jobs()

    assert len(jobs) == 2
    assert jobs[0]["name"] == "build-api"
    assert jobs[0]["status"] == "success"
    assert jobs[1]["name"] == "deploy"
    assert jobs[1]["status"] == "failure"


def test_get_jenkins_jobs_structure():
    mock_server = MagicMock()
    mock_server.get_jobs.return_value = [
        {"name": "ci", "url": "http://j/job/ci/", "color": "notbuilt"},
    ]
    with patch("ui.jobs_handler.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.jobs_handler.get_settings", return_value=_mock_settings()):
        jobs = get_jenkins_jobs()

    job = jobs[0]
    assert "name" in job
    assert "url" in job
    assert "status" in job
    assert "last_build_number" in job
    assert "last_build_result" in job
    assert job["last_build_number"] is None
    assert job["last_build_result"] is None


def test_get_jenkins_jobs_empty_when_no_credentials():
    with patch("ui.jobs_handler.get_settings", return_value=_mock_settings(url="", token="")):
        jobs = get_jenkins_jobs()
    assert jobs == []


def test_get_jenkins_jobs_returns_empty_on_connection_error():
    mock_server = MagicMock()
    mock_server.get_jobs.side_effect = Exception("Connection refused")
    with patch("ui.jobs_handler.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.jobs_handler.get_settings", return_value=_mock_settings()):
        jobs = get_jenkins_jobs()
    assert jobs == []


def test_get_jenkins_jobs_empty_response():
    mock_server = MagicMock()
    mock_server.get_jobs.return_value = []
    with patch("ui.jobs_handler.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.jobs_handler.get_settings", return_value=_mock_settings()):
        jobs = get_jenkins_jobs()
    assert jobs == []


# ── trigger_job ───────────────────────────────────────────────────────────────

def test_trigger_job_success():
    mock_server = MagicMock()
    with patch("ui.jobs_handler.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.jobs_handler.get_settings", return_value=_mock_settings()):
        result = trigger_job("my-job")
    assert result == {"ok": True}
    mock_server.build_job.assert_called_once_with("my-job")


def test_trigger_job_jenkins_exception():
    mock_server = MagicMock()
    mock_server.build_job.side_effect = jenkins_lib.JenkinsException("Job not found")
    with patch("ui.jobs_handler.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.jobs_handler.get_settings", return_value=_mock_settings()):
        result = trigger_job("missing-job")
    assert result["ok"] is False
    assert "Job not found" in result["error"]


def test_trigger_job_unexpected_exception():
    mock_server = MagicMock()
    mock_server.build_job.side_effect = RuntimeError("Unexpected error")
    with patch("ui.jobs_handler.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.jobs_handler.get_settings", return_value=_mock_settings()):
        result = trigger_job("my-job")
    assert result["ok"] is False
    assert "Unexpected error" in result["error"]
