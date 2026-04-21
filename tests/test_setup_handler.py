import pytest
from ui.setup_handler import validate_setup_payload, SetupError


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
