import logging
import asyncio
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from config import get_settings, validate_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    validate_config(settings)
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
    """Fetch console log + Jenkinsfile from Jenkins and run the full analysis pipeline."""
    from config import get_settings
    import xml.etree.ElementTree as ET

    settings = get_settings()

    console_log = ""
    jenkinsfile = ""

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

            try:
                config_xml = server.get_job_config(job)
                tree = ET.fromstring(config_xml)
                script_el = tree.find('.//script')
                if script_el is not None and script_el.text:
                    jenkinsfile = script_el.text.strip()
                    logger.info("[notification] Extracted Jenkinsfile: %d chars", len(jenkinsfile))
            except Exception as e:
                logger.warning("[notification] Could not fetch Jenkinsfile: %s", e)

        except Exception as e:
            logger.warning("[notification] Could not fetch console log: %s", e)

    synthetic_payload = {
        "job_name":     job,
        "build_number": build,
        "failed_stage": _detect_failed_stage(console_log),
        "status":       "FAILURE",
        "stages":       _detect_stages(console_log),
        "log":          console_log[-8000:] if console_log else "No log available",
        "jenkinsfile":  jenkinsfile,
    }

    _process_failure_sync(synthetic_payload, "jenkins")


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


_INTERNAL_STAGES = frozenset({
    "Declarative: Post Actions",
    "Declarative: Checkout SCM",
    "Post Actions",
})

# Matches the start of a named stage block: [Pipeline] { (StageName)
_STAGE_OPEN_RE  = re.compile(r'^\[Pipeline\] \{ \((.+?)\)\s*$')
# Matches closing brace for a stage
_STAGE_CLOSE_RE = re.compile(r'^\[Pipeline\] \}')
# Error indicators that signal a stage actually failed (not just was skipped)
_STAGE_ERROR_RE = re.compile(
    r'(?:^ERROR\b|: not found$|command not found|exit code [1-9]|FAILED|Exception|'
    r'Build step .* failed|returned exit code|fatal:|error:)',
    re.IGNORECASE | re.MULTILINE,
)
# Jenkins declarative: stage was skipped because an earlier stage failed
_SKIP_RE = re.compile(r'Stage ".+?" skipped due to earlier failure', re.IGNORECASE)


def _parse_stage_blocks(console_log: str) -> list[tuple[str, str]]:
    """
    Parse console log into a list of (stage_name, block_text) tuples,
    preserving order and excluding internal Jenkins stages.

    Each block_text is the text from the opening [Pipeline] { (Name) line
    up to (but not including) the corresponding [Pipeline] } line.
    """
    lines = console_log.splitlines()
    result: list[tuple[str, str]] = []
    depth = 0
    current_name: str | None = None
    current_lines: list[str] = []

    for line in lines:
        open_match = _STAGE_OPEN_RE.match(line.rstrip())
        if open_match:
            stage_name = open_match.group(1)
            if stage_name not in _INTERNAL_STAGES:
                if current_name is not None:
                    result.append((current_name, "\n".join(current_lines)))
                current_name = stage_name
                current_lines = [line]
                depth = 1
                continue

        if current_name is not None:
            if _STAGE_OPEN_RE.match(line.rstrip()):
                depth += 1
            elif _STAGE_CLOSE_RE.match(line.rstrip()):
                depth -= 1
                if depth <= 0:
                    result.append((current_name, "\n".join(current_lines)))
                    current_name = None
                    current_lines = []
                    depth = 0
                    continue
            current_lines.append(line)

    if current_name is not None:
        result.append((current_name, "\n".join(current_lines)))

    return result


def _detect_stages(console_log: str) -> list:
    """
    Parse stage names and statuses from the console log.
    Returns list of {"name": str, "status": "passed"|"failed"|"skipped"}.

    Uses block-aware parsing: each stage's own text is examined for errors
    and skip markers so that a global ERROR at the end of the log does not
    incorrectly attribute the failure to a later (skipped) stage.
    """
    if not console_log:
        return []

    blocks = _parse_stage_blocks(console_log)
    if not blocks:
        return []

    result = []
    failed_seen = False
    creds_stage: str | None = None  # last stage that used withCredentials

    for name, block in blocks:
        if "withCredentials" in block:
            creds_stage = name

        if failed_seen:
            result.append({"name": name, "status": "skipped"})
            continue

        if _SKIP_RE.search(block):
            result.append({"name": name, "status": "skipped"})
            continue

        if _STAGE_ERROR_RE.search(block):
            result.append({"name": name, "status": "failed"})
            failed_seen = True
        else:
            result.append({"name": name, "status": "passed"})

    # Jenkins withCredentials throws after the stage block closes — the error
    # lands in the tail of the log, not inside the block. Detect and re-attribute.
    _CREDS_TAIL_RE = re.compile(
        r'Could not find credentials entry with ID|CredentialsNotFoundException',
        re.IGNORECASE,
    )
    if not failed_seen and creds_stage and _CREDS_TAIL_RE.search(console_log):
        for entry in result:
            if entry["name"] == creds_stage:
                entry["status"] = "failed"
                failed_seen = True
            elif failed_seen:
                entry["status"] = "skipped"

    return result


def _detect_failed_stage(console_log: str) -> str:
    """
    Return the name of the first stage that contains an error in its own block.
    Falls back to 'unknown'.
    """
    if not console_log:
        return "unknown"

    for stage in _detect_stages(console_log):
        if stage["status"] == "failed":
            return stage["name"]

    return "unknown"


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

        # Verification facts override LLM guess — crawler findings are deterministic,
        # LLM output is probabilistic. If the crawler found a mismatch/missing cred
        # and the LLM didn't pick it up, force the correct fix_type.
        if report.mismatched_tools and analysis.get("fix_type") != "configure_tool":
            analysis["fix_type"] = "configure_tool"
            analysis["confidence"] = max(analysis.get("confidence", 0.5), 0.85)
            if not analysis.get("fix_suggestion"):
                m = report.mismatched_tools[0]
                analysis["fix_suggestion"] = (
                    f"Rename tool reference from '{m.referenced}' to '{m.configured}' "
                    f"in the Jenkinsfile tools block."
                )
        elif report.missing_credentials and analysis.get("fix_type") != "configure_credential":
            analysis["fix_type"] = "configure_credential"
            analysis["confidence"] = max(analysis.get("confidence", 0.5), 0.82)
            if not analysis.get("fix_suggestion"):
                cid = report.missing_credentials[0]
                analysis["fix_suggestion"] = (
                    f"Create credential '{cid}' in Jenkins Global Credentials store "
                    f"(Manage Jenkins → Credentials)."
                )

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
                "missing_secrets": report.missing_secrets,
                "missing_runners": report.missing_runners,
                "unpinned_actions": report.unpinned_actions,
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

    If the payload contains a 'sim_verification' dict (for simulation/demo without
    live Jenkins), that data is used directly instead of hitting the crawler.
    """
    from verification.models import VerificationReport, ToolMismatch
    from config import get_settings
    settings = get_settings()

    # Simulation mode: caller injected verification data directly in payload
    sim = payload.get("sim_verification")
    if sim:
        report = VerificationReport(platform="jenkins")
        for m in sim.get("mismatched_tools", []):
            report.mismatched_tools.append(ToolMismatch(
                referenced=m["referenced"],
                configured=m["configured"],
                match_score=m.get("match_score", 0.91),
            ))
        report.missing_credentials.extend(sim.get("missing_credentials", []))
        report.missing_plugins.extend(sim.get("missing_plugins", []))
        logger.info("[verification] Using sim_verification: %d mismatches, %d missing creds",
                    len(report.mismatched_tools), len(report.missing_credentials))
        return report

    try:
        from verification.jenkins_crawler import verify_jenkins_tools
        jenkinsfile = payload.get("jenkinsfile", "")
        if jenkinsfile and settings.jenkins_url:
            auth = (settings.jenkins_user, settings.jenkins_token) if settings.jenkins_token else None
            report = verify_jenkins_tools(jenkinsfile, settings.jenkins_url, auth=auth)
        else:
            report = VerificationReport(platform="jenkins")
    except Exception as e:
        logger.warning("[verification] Failed (non-fatal): %s", e)
        report = VerificationReport(platform="jenkins")

    # Fallback: parse Jenkins compile-time "did you mean" hints from console log.
    # Jenkins reports these when a tool block references an unconfigured tool name.
    # Pattern: Tool type "maven" does not have an install of "Maven3" — did you mean "Maven-3"?
    if not report.mismatched_tools:
        console_log = payload.get("log", "")
        _DID_YOU_MEAN = re.compile(
            r'Tool type "([^"]+)" does not have an install of "([^"]+)"[^"]*"([^"]+)"',
            re.IGNORECASE,
        )
        for m in _DID_YOU_MEAN.finditer(console_log):
            tool_type, referenced, suggested = m.group(1), m.group(2), m.group(3)
            if suggested.lower() != "null":
                report.mismatched_tools.append(ToolMismatch(
                    referenced=referenced,
                    configured=suggested,
                    match_score=0.91,
                ))
                logger.info("[verification] Parsed tool mismatch from log: '%s' → '%s'",
                            referenced, suggested)

    return report


def _summarise(payload: dict, source: str) -> str:
    """Return a short log-friendly summary of the incoming event."""
    if source == "github":
        wr = payload.get("workflow_run", {})
        return f"{wr.get('repository', {}).get('full_name')} / {wr.get('name')} #{wr.get('run_number')}"
    job = payload.get("job_name") or payload.get("name", "unknown-job")
    build = payload.get("build_number") or payload.get("number", "?")
    return f"{job} #{build}"
