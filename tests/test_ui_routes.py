import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
from webhook.server import app


client = TestClient(app)


def test_dashboard_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # React build title — matches <title>DevOps AI Agent</title>
    assert "devops ai agent" in response.text.lower()


def test_health_still_works():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_setup_invalid_payload_returns_422():
    response = client.post("/api/setup", json={})
    assert response.status_code == 422


def test_setup_valid_payload():
    with patch("ui.setup_handler.save_credentials") as mock_save:
        response = client.post("/api/setup", json={
            "jenkins_url": "http://localhost:8080",
            "jenkins_user": "admin",
            "jenkins_token": "token123",
        })
    assert response.status_code == 200
    assert response.json()["ok"] is True
    mock_save.assert_called_once()


def test_api_jobs_returns_list():
    with patch("ui.jobs_handler.get_jenkins_jobs", return_value=[
        {"name": "build-api", "url": "http://j/job/build-api/", "status": "failure",
         "last_build_number": 42, "last_build_result": "FAILURE"}
    ]):
        response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["name"] == "build-api"


def test_api_chat_returns_text():
    with patch("ui.chat_handler.handle_chat", return_value=iter(["Hello from LLM"])):
        response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert "Hello from LLM" in response.text


def test_api_fix_missing_fields_returns_422():
    response = client.post("/api/fix", json={})
    assert response.status_code == 422


def test_api_fix_executes_and_returns_result():
    with patch("agent.fix_executor.execute_fix") as mock_fix, \
         patch("agent.audit_log.log_fix"):
        mock_fix.return_value = MagicMock(success=True, fix_type="retry", detail="re-queued")
        response = client.post("/api/fix", json={
            "fix_type": "retry",
            "job_name": "build-api",
            "build_number": "42",
        })
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_api_fix_credential_fields_pass_through():
    with patch("agent.fix_executor.execute_fix") as mock_fix, \
         patch("agent.audit_log.log_fix"):
        mock_fix.return_value = MagicMock(
            success=True, fix_type="configure_credential", detail="created"
        )
        response = client.post("/api/fix", json={
            "fix_type": "configure_credential",
            "job_name": "my-job",
            "build_number": "1",
            "credential_id": "MY_TOKEN",
            "credential_type": "secret_text",
            "secret_value": "s3cr3t",
            "username": None,
            "password": None,
            "ssh_username": None,
            "private_key": None,
        })
    assert response.status_code == 200
    call_kwargs = mock_fix.call_args[1]
    assert call_kwargs.get("secret_value") == "s3cr3t"


def test_build_log_returns_text():
    mock_server = MagicMock()
    mock_server.get_build_console_output.return_value = "Started by user admin\n[Pipeline] Start of Pipeline\n"

    with patch("ui.routes.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.routes.get_settings") as mock_settings:
        mock_settings.return_value.jenkins_url = "http://localhost:8080"
        mock_settings.return_value.jenkins_user = "admin"
        mock_settings.return_value.jenkins_token = "token"
        response = client.get("/api/build-log?job=my-job&build=42")

    assert response.status_code == 200
    data = response.json()
    assert "log" in data
    assert "Started by user admin" in data["log"]


def test_build_log_jenkins_not_configured():
    with patch("ui.routes.get_settings") as mock_settings:
        mock_settings.return_value.jenkins_url = ""
        mock_settings.return_value.jenkins_token = ""
        response = client.get("/api/build-log?job=my-job&build=42")
    assert response.status_code == 503


def test_build_log_not_found():
    import jenkins as jenkins_lib
    mock_server = MagicMock()
    mock_server.get_build_console_output.side_effect = jenkins_lib.NotFoundException()

    with patch("ui.routes.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.routes.get_settings") as mock_settings:
        mock_settings.return_value.jenkins_url = "http://localhost:8080"
        mock_settings.return_value.jenkins_user = "admin"
        mock_settings.return_value.jenkins_token = "token"
        response = client.get("/api/build-log?job=my-job&build=42")

    assert response.status_code == 404


def test_commit_missing_fields_returns_422():
    response = client.post("/api/commit", json={})
    assert response.status_code == 422


def test_commit_jenkins_success():
    with patch("copilot.jenkins_configurator.create_job", return_value="http://jenkins/job/python-ci-pipeline/") as mock_create:
        response = client.post("/api/commit", json={
            "platform": "jenkins",
            "content": "pipeline { stages { stage('Build') { steps { sh 'make' } } } }",
            "description": "Python CI pipeline with Docker",
            "apply_to_jenkins": True,
        })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["job_name"] == "python-ci-pipeline-with-docker"
    assert data["job_url"] == "http://jenkins/job/python-ci-pipeline/"
    mock_create.assert_called_once()


def test_commit_jenkins_failure_returns_success_false():
    with patch("copilot.jenkins_configurator.create_job", side_effect=Exception("Jenkins unreachable")):
        response = client.post("/api/commit", json={
            "platform": "jenkins",
            "content": "pipeline { stages { stage('Build') { steps { sh 'make' } } } }",
            "description": "Python CI pipeline",
            "apply_to_jenkins": True,
        })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Jenkins unreachable" in data["detail"]


def test_commit_slugifies_description():
    with patch("copilot.jenkins_configurator.create_job", return_value="http://jenkins/job/my-node-app/"):
        response = client.post("/api/commit", json={
            "platform": "jenkins",
            "content": "pipeline { stages { stage('Build') { steps { sh 'npm build' } } } }",
            "description": "My Node.js App!! (v2) with Docker & ECR",
            "apply_to_jenkins": True,
        })
    assert response.status_code == 200
    data = response.json()
    assert data["job_name"] == "my-nodejs-app-v2-with-docker-ecr"


def test_commit_explicit_job_name_overrides_slugify():
    with patch("copilot.jenkins_configurator.create_job", return_value="http://jenkins/job/my-custom-name/") as mock_create:
        response = client.post("/api/commit", json={
            "platform": "jenkins",
            "content": "pipeline { stages { stage('Build') { steps { sh 'make' } } } }",
            "description": "Some long description that would slugify badly",
            "apply_to_jenkins": True,
            "job_name": "my-custom-name",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["job_name"] == "my-custom-name"
    mock_create.assert_called_once_with("my-custom-name", ANY, ANY)


def test_chat_handler_includes_history_with_role_labels():
    """History must include role labels User: and Assistant: in the prompt."""
    from ui.chat_handler import handle_chat

    mock_provider = MagicMock()
    mock_provider.stream_complete.return_value = iter(["answer"])

    with patch('ui.chat_handler.get_provider', return_value=mock_provider):
        chunks = list(handle_chat(
            "What is Jenkins?",
            history=[
                {"role": "user",      "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        ))

    assert chunks == ["answer"]
    prompt_used = mock_provider.stream_complete.call_args[0][0]
    assert "Hello" in prompt_used
    assert "Hi there!" in prompt_used
    assert "What is Jenkins?" in prompt_used
    assert "User:" in prompt_used
    assert "Assistant:" in prompt_used
