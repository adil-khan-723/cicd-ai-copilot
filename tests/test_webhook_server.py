# tests/test_webhook_server.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from webhook.server import app

client = TestClient(app)

MOCK_PAYLOAD = {
    "job_name": "test-job",
    "build_number": "1",
    "failed_stage": "Build",
    "status": "FAILURE",
    "stages": [{"name": "Build", "status": "failed"}],
    "log": "error: command not found",
}


def test_analysis_complete_includes_verification():
    """analysis_complete SSE event must include a verification key."""
    from ui.event_bus import bus

    published = []
    original_publish = bus.publish

    def capture(event):
        published.append(event)
        original_publish(event)

    mock_provider = MagicMock()
    mock_provider.complete.return_value = '{"root_cause":"test","fix_suggestion":"retry","fix_type":"retry","confidence":0.9}'

    with patch.object(bus, "publish", side_effect=capture), \
         patch("analyzer.llm_client.get_provider", return_value=mock_provider), \
         patch("webhook.server._run_verification") as mock_verify:
        from verification.models import VerificationReport
        mock_verify.return_value = VerificationReport(
            platform="jenkins",
            missing_credentials=["MY_SECRET"],
        )
        from webhook.server import _process_failure_sync
        _process_failure_sync(MOCK_PAYLOAD, "jenkins")

    analysis_events = [e for e in published if e.get("type") == "analysis_complete"]
    assert len(analysis_events) == 1
    ev = analysis_events[0]
    assert "verification" in ev
    v = ev["verification"]
    assert "matched_tools" in v
    assert "mismatched_tools" in v
    assert "missing_plugins" in v
    assert "missing_credentials" in v
    assert "errors" in v
    assert "MY_SECRET" in v["missing_credentials"]
