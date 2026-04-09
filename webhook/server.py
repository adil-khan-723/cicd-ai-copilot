import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from config import get_settings

logger = logging.getLogger(__name__)

app = FastAPI(title="DevOps AI Agent — Webhook Server")


@app.on_event("startup")
async def startup():
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level))
    logger.info("Webhook server started on port %s", settings.webhook_port)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/pipeline-failure")
async def pipeline_failure(request: Request):
    """
    Receives pipeline failure events from Jenkins or GitHub Actions.
    Validates the webhook signature, then queues the event for processing.
    """
    settings = get_settings()

    # Detect source from headers
    source = _detect_source(request)

    # Validate signature
    if source == "github":
        from webhook.validators import validate_github_webhook
        await validate_github_webhook(request, settings.webhook_secret)
    elif source == "jenkins":
        from webhook.validators import validate_jenkins_webhook
        await validate_jenkins_webhook(request, settings.webhook_secret)

    payload = await request.json()
    logger.info("Received %s failure event: %s", source, _summarise(payload, source))

    # Hand off to processing pipeline (wired in Phase 1 integration, Increment 11)
    return JSONResponse({"status": "received", "source": source})


def _detect_source(request: Request) -> str:
    """Identify whether the webhook came from GitHub Actions or Jenkins."""
    if request.headers.get("X-GitHub-Event"):
        return "github"
    if request.headers.get("X-Jenkins-Event") or request.headers.get("X-Jenkins-Signature"):
        return "jenkins"
    # Default — accept without strict validation during local dev
    return "unknown"


def _summarise(payload: dict, source: str) -> str:
    """Return a short log-friendly summary of the incoming event."""
    if source == "github":
        wr = payload.get("workflow_run", {})
        return f"{wr.get('repository', {}).get('full_name')} / {wr.get('name')} #{wr.get('run_number')}"
    job = payload.get("job_name") or payload.get("name", "unknown-job")
    build = payload.get("build_number") or payload.get("number", "?")
    return f"{job} #{build}"
