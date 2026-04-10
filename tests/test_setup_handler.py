import pytest
from ui.setup_handler import validate_setup_payload, SetupError


def test_valid_payload_passes():
    payload = {
        "github_repo": "adil-khan-723/build-api",
        "github_token": "ghp_abc123def456",
        "jenkins_url": "http://localhost:8080",
        "jenkins_user": "admin",
        "jenkins_token": "abc123",
    }
    validate_setup_payload(payload)  # should not raise


def test_invalid_github_repo_raises():
    with pytest.raises(SetupError, match="github_repo"):
        validate_setup_payload({
            "github_repo": "not-a-valid-repo",
            "github_token": "ghp_abc",
            "jenkins_url": "http://localhost:8080",
            "jenkins_user": "admin",
            "jenkins_token": "abc",
        })


def test_invalid_github_token_raises():
    with pytest.raises(SetupError, match="github_token"):
        validate_setup_payload({
            "github_repo": "owner/repo",
            "github_token": "not-a-pat",
            "jenkins_url": "http://localhost:8080",
            "jenkins_user": "admin",
            "jenkins_token": "abc",
        })


def test_invalid_jenkins_url_raises():
    with pytest.raises(SetupError, match="jenkins_url"):
        validate_setup_payload({
            "github_repo": "owner/repo",
            "github_token": "ghp_abc",
            "jenkins_url": "not-a-url",
            "jenkins_user": "admin",
            "jenkins_token": "abc",
        })


def test_missing_field_raises():
    with pytest.raises(SetupError, match="jenkins_user"):
        validate_setup_payload({
            "github_repo": "owner/repo",
            "github_token": "ghp_abc",
            "jenkins_url": "http://localhost:8080",
            "jenkins_user": "",
            "jenkins_token": "abc",
        })
