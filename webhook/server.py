import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level))
    logger.info("Webhook server started on port %s", settings.webhook_port)

    from ui.routes import _jenkins_health_monitor
    import ui.routes as _ui_routes
    _ui_routes._jenkins_monitor_task = asyncio.create_task(_jenkins_health_monitor())
    logger.info("Jenkins health monitor started (10s poll)")

    yield

    import ui.routes as _ui_routes
    if _ui_routes._jenkins_monitor_task:
        _ui_routes._jenkins_monitor_task.cancel()


app = FastAPI(title="DevOps AI Agent — Webhook Server", lifespan=lifespan)

from ui.routes import router as ui_router
from fastapi.staticfiles import StaticFiles
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory="ui/static"), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/jenkins-notification")
async def jenkins_notification(request: Request, background_tasks: BackgroundTasks):
    """
    Receives build notifications from the Jenkins Notification Plugin.
    Fires for ALL jobs automatically — no post blocks needed in Jenkinsfiles.

    Payload format:
      {"name":"job","url":"...","build":{"number":1,"phase":"FINALIZED","status":"FAILURE","full_url":"..."}}

    Only acts on FINALIZED phase (not STARTED/COMPLETED) to avoid duplicates.
    Fetches the console log from Jenkins API and runs the full analysis pipeline.
    """
    payload = await request.json()

    phase  = payload.get("build", {}).get("phase", "").upper()
    status = payload.get("build", {}).get("status", "").upper()
    job    = payload.get("name", "unknown")
    build  = str(payload.get("build", {}).get("number", "0"))

    logger.info("Notification plugin: job=%s build=%s phase=%s status=%s", job, build, phase, status)

    # Only act on FINALIZED — plugin also sends STARTED and COMPLETED
    if phase != "FINALIZED":
        return {"status": "ignored", "reason": f"phase={phase}"}

    if status == "FAILURE" or status == "ABORTED" or status == "UNSTABLE":
        background_tasks.add_task(_process_notification_failure, job, build, payload)
    elif status == "SUCCESS":
        background_tasks.add_task(_process_notification_success, job, build)

    return {"status": "received", "job": job, "build": build, "status_code": status}


async def _process_notification_failure(job: str, build: str, payload: dict) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _process_notification_failure_sync, job, build, payload)


def _process_notification_failure_sync(job: str, build: str, payload: dict) -> None:
    """Fetch console log from Jenkins and run the full analysis pipeline."""
    from ui.event_bus import bus
    from config import get_settings

    settings = get_settings()

    try:
        # Fetch console log from Jenkins API
        console_log = ""
        if settings.jenkins_url and settings.jenkins_token:
            try:
                import jenkins as jenkins_lib
                server = jenkins_lib.Jenkins(
                    settings.jenkins_url,
                    username=settings.jenkins_user,
                    password=settings.jenkins_token,
                )
                console_log = server.get_build_console_output(job, int(build))
                logger.info("[notification] Fetched console log: %d chars for %s #%s", len(console_log), job, build)
            except Exception as e:
                logger.warning("[notification] Could not fetch console log: %s", e)

        # Build a synthetic webhook payload and run the existing pipeline
        synthetic_payload = {
            "job_name":     job,
            "build_number": build,
            "failed_stage": _detect_failed_stage(console_log),
            "status":       "FAILURE",
            "stages":       _detect_stages(console_log),
            "log":          console_log[-8000:] if console_log else "No log available",
        }

        # Reuse the existing sync pipeline
        _process_failure_sync(synthetic_payload, "jenkins")

    except Exception as e:
        logger.exception("[notification] Error processing failure for %s #%s: %s", job, build, e)
        from ui.event_bus import bus
        bus.publish({
            "type": "step", "job": job, "build": build,
            "stage": "PIPELINE_ERROR", "detail": str(e), "status": "failed",
        })


async def _process_notification_success(job: str, build: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _process_notification_success_sync, job, build)


def _process_notification_success_sync(job: str, build: str) -> None:
    from ui.event_bus import bus

    previous_failed_build = None
    previous_root_cause   = None
    for event in reversed(list(bus._history)):
        if event.get("type") == "analysis_complete" and event.get("job") == job:
            previous_failed_build = event.get("build")
            previous_root_cause   = event.get("root_cause")
            break

    bus.publish({
        "type":                  "build_success",
        "job":                   job,
        "build":                 build,
        "previous_failed_build": previous_failed_build,
        "previous_root_cause":   previous_root_cause,
    })
    logger.info("[notification] Success published: %s #%s", job, build)


def _detect_failed_stage(console_log: str) -> str:
    """
    Try to extract which stage failed from the console log.
    Looks for '[Pipeline] { (StageName)' lines followed by error indicators.
    Falls back to 'unknown'.
    """
    if not console_log:
        return "unknown"

    import re
    # Find all stage names and their positions
    stage_pattern = re.compile(r'\[Pipeline\] \{ \((.+?)\)')
    error_pattern = re.compile(r'(?:ERROR:|FAILED|error:|Build step.*failed|exit code \d+[^0])', re.IGNORECASE)

    stages = list(stage_pattern.finditer(console_log))
    if not stages:
        return "unknown"

    # Find position of first error
    error_match = error_pattern.search(console_log)
    if not error_match:
        return stages[-1].group(1) if stages else "unknown"

    error_pos = error_match.start()

    # The failed stage is the last stage that started before the error
    failed_stage = "unknown"
    for match in stages:
        if match.start() < error_pos:
            name = match.group(1)
            # Skip internal Jenkins stages
            if name not in ("Declarative: Post Actions", "Declarative: Checkout SCM"):
                failed_stage = name
        else:
            break

    return failed_stage


def _detect_stages(console_log: str) -> list:
    """
    Parse stage names and statuses from the console log.
    Returns list of {"name": str, "status": "passed"|"failed"|"skipped"}.
    """
    if not console_log:
        return []

    import re
    stage_starts = re.findall(r'\[Pipeline\] \{ \((.+?)\)', console_log)
    # Filter internal stages
    internal = {"Declarative: Post Actions", "Declarative: Checkout SCM", "Post Actions"}
    stages = [s for s in stage_starts if s not in internal]

    if not stages:
        return []

    failed_stage = _detect_failed_stage(console_log)
    result = []
    failed_seen = False
    for name in stages:
        if name == failed_stage:
            result.append({"name": name, "status": "failed"})
            failed_seen = True
        elif failed_seen:
            result.append({"name": name, "status": "skipped"})
        else:
            result.append({"name": name, "status": "passed"})

    return result


@app.post("/webhook/pipeline-success")
async def pipeline_success(request: Request):
    """
    Receives pipeline success events. Looks up the most recent failure analysis
    for this job from EventBus history and emits a build_success SSE event so
    the UI can show a success card and prompt to discard old failure cards.
    """
    from ui.event_bus import bus

    payload = await request.json()
    job  = payload.get("job_name", "unknown")
    build = payload.get("build_number", "0")

    # Find the most recent analysis_complete for this job in history
    previous_failed_build = None
    previous_root_cause   = None
    for event in reversed(list(bus._history)):
        if event.get("type") == "analysis_complete" and event.get("job") == job:
            previous_failed_build = event.get("build")
            previous_root_cause   = event.get("root_cause")
            break

    bus.publish({
        "type": "build_success",
        "job":  job,
        "build": build,
        "previous_failed_build": previous_failed_build,
        "previous_root_cause":   previous_root_cause,
    })
    logger.info("Pipeline success: %s #%s", job, build)
    return {"status": "received"}


@app.post("/webhook/pipeline-failure")
async def pipeline_failure(request: Request, background_tasks: BackgroundTasks):
    """
    Receives pipeline failure events from Jenkins.
    Validates the webhook signature, returns 200 immediately, then
    runs the full analysis pipeline in the background.
    """
    settings = get_settings()

    if settings.webhook_secret:
        from webhook.validators import validate_jenkins_webhook
        await validate_jenkins_webhook(request, settings.webhook_secret)

    payload = await request.json()
    job = payload.get("job_name") or payload.get("name", "unknown-job")
    build = payload.get("build_number") or payload.get("number", "?")
    logger.info("Received jenkins failure event: %s #%s", job, build)

    background_tasks.add_task(_process_failure, payload, "jenkins")
    return JSONResponse({"status": "received", "source": "jenkins"})


async def _process_failure(payload: dict, source: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _process_failure_sync, payload, source)


def _process_failure_sync(payload: dict, source: str) -> None:
    from parser.pipeline_parser import parse_failure
    from parser.log_extractor import extract_failed_logs
    from parser.log_cleaner import clean_log
    from analyzer.context_builder import build_context
    from analyzer.llm_client import analyze
    from ui.event_bus import bus

    try:
        # Step 1: Parse webhook payload
        ctx = parse_failure(payload, source=source)
        logger.info("[pipeline] Parsed: %s #%s stage=%s", ctx.job_name, ctx.build_number, ctx.failed_stage)
        bus.publish({
            "type": "step", "job": ctx.job_name, "build": ctx.build_number,
            "stage": "WEBHOOK_RECEIVED",
            "detail": f"stage: {ctx.failed_stage}", "status": "done",
        })

        # Step 2: Extract and clean the failed stage log
        extracted = extract_failed_logs(ctx)
        cleaned = clean_log(extracted)
        logger.info("[pipeline] Cleaned log: %d chars", len(cleaned))
        bus.publish({
            "type": "step", "job": ctx.job_name, "build": ctx.build_number,
            "stage": "LOG_EXTRACTED",
            "detail": f"{len(cleaned)} chars after cleaning", "status": "done",
        })

        # Step 3: Tool verification (best-effort — never blocks the pipeline)
        report = _run_verification(ctx, payload)
        mismatch_count = len(getattr(report, "mismatched", []))
        bus.publish({
            "type": "step", "job": ctx.job_name, "build": ctx.build_number,
            "stage": "TOOL_VERIFICATION",
            "detail": f"{mismatch_count} mismatches found", "status": "done",
        })

        # Step 4: Build LLM context and analyze
        bus.publish({
            "type": "step", "job": ctx.job_name, "build": ctx.build_number,
            "stage": "CONTEXT_BUILT", "detail": "sending to LLM...", "status": "running",
        })
        context_str = build_context(cleaned, report, ctx)
        analysis = analyze(context_str)  # always returns a dict — never raises
        logger.info(
            "[pipeline] Analysis done: root_cause=%s confidence=%.2f fix_type=%s",
            analysis.get("root_cause", "")[:60],
            analysis.get("confidence", 0),
            analysis.get("fix_type"),
        )

        # Determine step status: if no LLM was available, mark as failed so UI shows it clearly
        llm_ok = analysis.get("confidence", 0) > 0 or analysis.get("fix_type") != "diagnostic_only"
        context_status = "done" if llm_ok else "failed"
        llm_status = "done" if llm_ok else "failed"

        bus.publish({
            "type": "step", "job": ctx.job_name, "build": ctx.build_number,
            "stage": "CONTEXT_BUILT", "detail": "context built", "status": context_status,
        })
        bus.publish({
            "type": "step", "job": ctx.job_name, "build": ctx.build_number,
            "stage": "LLM_ANALYSIS",
            "detail": analysis.get("root_cause", "")[:120],
            "fix_type": analysis.get("fix_type"),
            "confidence": analysis.get("confidence", 0),
            "status": llm_status,
        })

        # Step 5: Always emit analysis_complete so the UI card renders
        bus.publish({
            "type": "analysis_complete",
            "job": ctx.job_name,
            "build": ctx.build_number,
            "failed_stage": ctx.failed_stage,
            "root_cause": analysis.get("root_cause", ""),
            "fix_suggestion": analysis.get("fix_suggestion", ""),
            "fix_type": analysis.get("fix_type"),
            "confidence": analysis.get("confidence", 0),
            "log_excerpt": cleaned[:400],
            "pipeline_stages": [
                {"name": name, "status": status}
                for name, status in ctx.pipeline_stages
            ],
            "verification": {
                "matched_tools": report.matched_tools,
                "mismatched_tools": [
                    {
                        "referenced": m.referenced,
                        "configured": m.configured,
                        "match_score": m.match_score,
                    }
                    for m in report.mismatched_tools
                ],
                "missing_plugins": report.missing_plugins,
                "missing_credentials": report.missing_credentials,
                "errors": report.errors,
            },
        })

    except Exception as e:
        logger.exception("[pipeline] Unhandled error in failure processing: %s", e)
        # Best-effort: tell the UI something went wrong so it doesn't hang
        try:
            from ui.event_bus import bus
            bus.publish({
                "type": "step",
                "job": payload.get("job_name", "unknown"),
                "build": str(payload.get("build_number", "0")),
                "stage": "PIPELINE_ERROR",
                "detail": f"Internal error: {e}",
                "status": "failed",
            })
        except Exception:
            pass


def _run_verification(ctx, payload: dict) -> "VerificationReport":
    """
    Run Jenkins or GitHub verification — returns empty report on any error.
    Verification is always best-effort and never blocks the pipeline.
    """
    from verification.models import VerificationReport
    from config import get_settings
    settings = get_settings()

    try:
        from verification.jenkins_crawler import verify_jenkins_tools
        jenkinsfile = payload.get("jenkinsfile", "")
        if jenkinsfile and settings.jenkins_url:
            auth = (settings.jenkins_user, settings.jenkins_token) if settings.jenkins_token else None
            return verify_jenkins_tools(jenkinsfile, settings.jenkins_url, auth=auth)
    except Exception as e:
        logger.warning("[verification] Failed (non-fatal): %s", e)

    return VerificationReport(platform="jenkins")


def _summarise(payload: dict, source: str) -> str:
    """Return a short log-friendly summary of the incoming event."""
    if source == "github":
        wr = payload.get("workflow_run", {})
        return f"{wr.get('repository', {}).get('full_name')} / {wr.get('name')} #{wr.get('run_number')}"
    job = payload.get("job_name") or payload.get("name", "unknown-job")
    build = payload.get("build_number") or payload.get("number", "?")
    return f"{job} #{build}"
