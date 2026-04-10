import logging
import asyncio
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from config import get_settings

logger = logging.getLogger(__name__)

app = FastAPI(title="DevOps AI Agent — Webhook Server")

from ui.routes import router as ui_router
from fastapi.staticfiles import StaticFiles
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory="ui/static"), name="static")


@app.on_event("startup")
async def startup():
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level))
    logger.info("Webhook server started on port %s", settings.webhook_port)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/pipeline-failure")
async def pipeline_failure(request: Request, background_tasks: BackgroundTasks):
    """
    Receives pipeline failure events from Jenkins or GitHub Actions.
    Validates the webhook signature, returns 200 immediately, then
    runs the full analysis pipeline in the background.
    """
    settings = get_settings()

    # Detect source from headers
    source = _detect_source(request)

    # Validate signature (skip if no secret configured — dev mode)
    if settings.webhook_secret:
        if source == "github":
            from webhook.validators import validate_github_webhook
            await validate_github_webhook(request, settings.webhook_secret)
        elif source == "jenkins":
            from webhook.validators import validate_jenkins_webhook
            await validate_jenkins_webhook(request, settings.webhook_secret)

    payload = await request.json()
    logger.info("Received %s failure event: %s", source, _summarise(payload, source))

    # Return immediately — process in background
    background_tasks.add_task(_process_failure, payload, source)
    return JSONResponse({"status": "received", "source": source})


async def _process_failure(payload: dict, source: str) -> None:
    """
    Full reactive pipeline:
    parse → extract logs → clean → verify → build context → LLM → Slack
    """
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _process_failure_sync, payload, source)


def _process_failure_sync(payload: dict, source: str) -> None:
    from parser.pipeline_parser import parse_failure
    from parser.log_extractor import extract_failed_logs
    from parser.log_cleaner import clean_log
    from verification.models import VerificationReport
    from analyzer.context_builder import build_context
    from analyzer.llm_client import analyze
    from slack.notifier import send_failure_alert, update_with_analysis
    from slack.message_templates import failure_alert_blocks

    try:
        # Step 1: Parse webhook payload
        ctx = parse_failure(payload, source=source)
        logger.info("[pipeline] Parsed: %s #%s stage=%s", ctx.job_name, ctx.build_number, ctx.failed_stage)

        # Step 2: Extract and clean the failed stage log
        extracted = extract_failed_logs(ctx)
        cleaned = clean_log(extracted)
        logger.info("[pipeline] Cleaned log: %d chars", len(cleaned))

        # Step 3: Tool verification (best-effort — never blocks the pipeline)
        report = _run_verification(ctx, payload)

        # Step 4: Post initial Slack alert (analysis pending)
        ts = send_failure_alert(ctx, cleaned, report=report)
        if not ts:
            logger.error("[pipeline] Failed to post Slack alert — aborting")
            return

        logger.info("[pipeline] Slack alert posted: ts=%s", ts)

        # Step 5: Build LLM context and analyze
        context_str = build_context(cleaned, report, ctx)
        analysis = analyze(context_str)
        logger.info(
            "[pipeline] Analysis done: root_cause=%s confidence=%.2f fix_type=%s",
            analysis.get("root_cause", "")[:60],
            analysis.get("confidence", 0),
            analysis.get("fix_type"),
        )

        # Step 6: Update Slack message with analysis + action buttons
        initial_blocks = failure_alert_blocks(ctx, cleaned, report=report)
        update_with_analysis(ts, initial_blocks, analysis)
        logger.info("[pipeline] Slack message updated with analysis")

    except Exception as e:
        logger.exception("[pipeline] Unhandled error in failure processing: %s", e)


def _run_verification(ctx, payload: dict) -> "VerificationReport":
    """
    Run Jenkins or GitHub verification — returns empty report on any error.
    Verification is always best-effort and never blocks the pipeline.
    """
    from verification.models import VerificationReport
    from config import get_settings
    settings = get_settings()

    try:
        if ctx.platform == "jenkins":
            from verification.jenkins_crawler import verify_jenkins_tools
            jenkinsfile = payload.get("jenkinsfile", "")
            if jenkinsfile and settings.jenkins_url:
                auth = (settings.jenkins_user, settings.jenkins_token) if settings.jenkins_token else None
                return verify_jenkins_tools(jenkinsfile, settings.jenkins_url, auth=auth)

        elif ctx.platform == "github":
            from verification.actions_crawler import verify_actions_config
            workflow = payload.get("workflow_content", "")
            if workflow and ctx.repo and settings.github_token:
                return verify_actions_config(workflow, ctx.repo, github_token=settings.github_token)

    except Exception as e:
        logger.warning("[verification] Failed (non-fatal): %s", e)

    return VerificationReport(platform=ctx.platform)


def _detect_source(request: Request) -> str:
    """Identify whether the webhook came from GitHub Actions or Jenkins."""
    if request.headers.get("X-GitHub-Event"):
        return "github"
    if request.headers.get("X-Jenkins-Event") or request.headers.get("X-Jenkins-Signature"):
        return "jenkins"
    return "unknown"


def _summarise(payload: dict, source: str) -> str:
    """Return a short log-friendly summary of the incoming event."""
    if source == "github":
        wr = payload.get("workflow_run", {})
        return f"{wr.get('repository', {}).get('full_name')} / {wr.get('name')} #{wr.get('run_number')}"
    job = payload.get("job_name") or payload.get("name", "unknown-job")
    build = payload.get("build_number") or payload.get("number", "?")
    return f"{job} #{build}"
