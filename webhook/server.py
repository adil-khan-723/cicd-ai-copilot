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
        "log":          _slice_log(console_log, 8000) if console_log else "No log available",
        "_full_log":    console_log,  # unsliced — for tail-error detection in _run_verification
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
# Error indicators that signal a stage actually failed (not just was skipped).
# Deliberately narrow — avoids matching "0 failed" in test output, "error:" in URLs, etc.
_STAGE_ERROR_RE = re.compile(
    r'(?:^ERROR\b|\bProcess .* exit code [1-9]|\bcommand not found\b'
    r'|\bBuild step .* failed\b|\breturned exit code [1-9]'
    r'|\bException\b|\bFATAL\b'
    r'|^\+ .+: not found$'
    r'|: not found$'
    r'|\bpermission denied\b'
    r'|\bNo such DSL method\b'
    r'|\bCredentialsNotFoundException\b'
    r'|\bFlowInterruptedException\b)',
    re.IGNORECASE | re.MULTILINE,
)
# Jenkins declarative: stage was skipped because an earlier stage failed
_SKIP_RE = re.compile(r'Stage ".+?" skipped due to earlier failure', re.IGNORECASE)



def _slice_log(log: str, max_chars: int) -> str:
    """
    Return up to max_chars of the log.

    Strategy:
    - If log fits, return as-is.
    - If first error is in the top 30% of the log (compile-time / pre-stage failure),
      anchor there so the error isn't discarded. This handles CPS compile failures
      that appear before any stage block.
    - Otherwise take the tail — runtime errors (No such DSL method, credential failures,
      timeouts) appear at the end of the log after all stage blocks have run.
      Tail slicing preserves the stage blocks AND the error.
    """
    if len(log) <= max_chars:
        return log
    _anchor = re.compile(
        r'(No such DSL method|NoSuchMethodError|MultipleCompilationErrorsException'
        r'|startup failed:|WorkflowScript: \d+:|ERROR:|FAILED|Exception:|Caused by:)',
        re.IGNORECASE,
    )
    m = _anchor.search(log)
    if m and m.start() < len(log) * 0.30:
        # Error is near the top — anchor there (compile-time failure)
        start = max(0, m.start() - 200)
        return ("...[truncated]\n" if start > 0 else "") + log[start:start + max_chars]
    # Error is in the middle/tail — take the tail to preserve stage blocks + error
    return log[-max_chars:]


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
        # Compile-time failure: Jenkins never opened any stage block.
        # Synthesize a virtual stage so the UI shows something useful.
        _COMPILE_ERROR_RE = re.compile(
            r'MultipleCompilationErrorsException|startup failed:|WorkflowScript:.*error',
            re.IGNORECASE,
        )
        if _COMPILE_ERROR_RE.search(console_log):
            return [{"name": "Pipeline Startup", "status": "failed"}]
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

    # Some errors land in the log AFTER all stage blocks close (Jenkins reports them
    # at pipeline teardown). Re-attribute to the last stage that ran before the error.
    # Patterns:
    #   - withCredentials: CredentialsNotFoundException
    #   - No such DSL method: step name typo, error emitted after stage closes
    #   - No maven named X: tool resolution failure reported post-stage
    _TAIL_ERROR_RE = re.compile(
        r'Could not find credentials entry with ID|CredentialsNotFoundException'
        r'|No such DSL method\b'
        r'|No maven named\b|No tool named\b'
        r'|FlowInterruptedException',
        re.IGNORECASE,
    )
    if not failed_seen and _TAIL_ERROR_RE.search(console_log):
        # Find the last stage that was not skipped — that's the one that failed
        for entry in reversed(result):
            if entry["status"] == "passed":
                entry["status"] = "failed"
                failed_seen = True
                break
        # Mark everything after it as skipped
        found = False
        for entry in result:
            if entry["status"] == "failed" and not found:
                found = True
            elif found:
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
        context_str = build_context(cleaned, report, ctx, jenkinsfile=payload.get("jenkinsfile", ""))
        analysis = analyze(context_str)  # always returns a dict — never raises

        # ── Syntax/DSL-error sentinel — checked before verification overrides ───────
        # Covers both compile-time (MultipleCompilationErrorsException, startup failed)
        # and runtime DSL errors (No such DSL method) which appear in the full log tail,
        # not necessarily inside the extracted stage block.
        # Search both cleaned (stage block) AND the full sliced log so nothing is missed.
        _GROOVY_COMPILE_RE = re.compile(
            r"MultipleCompilationErrorsException"
            r"|No such DSL method\b"
            r"|Expected a step\b"
            r"|unexpected token\b"
            r"|unable to resolve class\b"
            r"|startup failed:"
            r"|WorkflowScript: \d+: ",
            re.IGNORECASE,
        )
        _full_log = payload.get("_full_log", payload.get("log", ""))
        _has_compile_error = bool(
            _GROOVY_COMPILE_RE.search(cleaned or "")
            or _GROOVY_COMPILE_RE.search(_full_log)
        )

        # Verification facts override LLM guess — crawler findings are deterministic,
        # LLM output is probabilistic. If the crawler found a mismatch/missing cred
        # and the LLM didn't pick it up, force the correct fix_type.
        # Skip when a compile error is present — syntax must be fixed first.
        if not _has_compile_error:
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

        # ── Confidence booster: Groovy/Jenkins compile error detected in log ──────
        # We do NOT extract bad/correct from the log ourselves — the LLM has the
        # Jenkinsfile source and is the sole authority on what is wrong and how to fix it.
        # Our only job here: if the log proves it's a compile/syntax error, ensure
        # confidence is high enough that Apply Fix is shown (not "Requires manual action").
        if _has_compile_error:
            if analysis.get("fix_type") == "fix_step_typo":
                # LLM correctly identified it — just make sure confidence is high
                analysis["confidence"] = max(analysis.get("confidence", 0.5), 0.92)
                # Populate bad_step/correct_step from LLM-provided bad_line/correct_line
                if analysis.get("bad_line") and not analysis.get("bad_step"):
                    analysis["bad_step"] = analysis["bad_line"]
                if analysis.get("correct_line") and not analysis.get("correct_step"):
                    analysis["correct_step"] = analysis["correct_line"]
                logger.info(
                    "[pipeline] Groovy compile error + LLM fix_step_typo — bad=%r correct=%r",
                    str(analysis.get("bad_step", ""))[:60],
                    str(analysis.get("correct_step", ""))[:60],
                )
            elif analysis.get("fix_type") == "diagnostic_only":
                # LLM saw a syntax error but couldn't produce bad_line/correct_line
                # (e.g. Jenkinsfile source was missing from context). Stay diagnostic.
                logger.info("[pipeline] Groovy compile error but LLM returned diagnostic_only — no Jenkinsfile source?")

        logger.info(
            "[pipeline] Analysis done: root_cause=%s confidence=%.2f fix_type=%s steps=%d",
            analysis.get("root_cause", "")[:60],
            analysis.get("confidence", 0),
            analysis.get("fix_type"),
            len(analysis.get("steps", [])),
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
            "steps": analysis.get("steps", []),
            "fix_type": analysis.get("fix_type"),
            "confidence": analysis.get("confidence", 0),
            "log_excerpt": cleaned[:400],
            "bad_step": analysis.get("bad_step") or analysis.get("bad_line"),
            "correct_step": analysis.get("correct_step") or analysis.get("correct_line"),
            "bad_image": analysis.get("bad_image"),
            "correct_image": analysis.get("correct_image"),
            "credential_type": analysis.get("credential_type"),
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

    # Fallback: parse tool mismatch hints from console log when crawler missed it.
    # Covers two Jenkins error formats:
    #   1. Compile-time: Tool type "maven" does not have an install of "Maven3" ... "Maven-3"?
    #   2. Runtime:      No maven named Maven3 found  (withMaven / tool() step failure)
    if not report.mismatched_tools:
        console_log = payload.get("log", "") or ""
        # Also search the full raw log from the notification payload (not just the slice)
        full_log = payload.get("_full_log", console_log)

        _DID_YOU_MEAN = re.compile(
            r'Tool type "([^"]+)" does not have an install of "([^"]+)"[^"]*"([^"]+)"',
            re.IGNORECASE,
        )
        for m in _DID_YOU_MEAN.finditer(full_log):
            tool_type, referenced, suggested = m.group(1), m.group(2), m.group(3)
            if suggested.lower() != "null":
                report.mismatched_tools.append(ToolMismatch(
                    referenced=referenced,
                    configured=suggested,
                    match_score=0.91,
                ))
                logger.info("[verification] Parsed tool mismatch (did-you-mean): '%s' → '%s'",
                            referenced, suggested)

        # Runtime format: "No maven named Maven3 found" — Jenkins knows the right name
        # from its own config; use the crawler-verified configured names if available.
        if not report.mismatched_tools:
            _NO_TOOL_RE = re.compile(r'No (\w+) named [\'"]?([^\'"]+?)[\'"]? found', re.IGNORECASE)
            for m in _NO_TOOL_RE.finditer(full_log):
                tool_type, referenced = m.group(1).lower(), m.group(2).strip()
                # Ask crawler for configured names of this tool type
                try:
                    from verification.jenkins_crawler import get_configured_tools
                    configured = get_configured_tools(
                        settings.jenkins_url,
                        auth=(settings.jenkins_user, settings.jenkins_token) if settings.jenkins_token else None,
                    )
                    matches = configured.get(tool_type, [])
                    if matches:
                        report.mismatched_tools.append(ToolMismatch(
                            referenced=referenced,
                            configured=matches[0],
                            match_score=0.88,
                        ))
                        logger.info("[verification] Parsed tool mismatch (no-tool-named): '%s' → '%s'",
                                    referenced, matches[0])
                except Exception:
                    pass

    return report


def _summarise(payload: dict, source: str) -> str:
    """Return a short log-friendly summary of the incoming event."""
    if source == "github":
        wr = payload.get("workflow_run", {})
        return f"{wr.get('repository', {}).get('full_name')} / {wr.get('name')} #{wr.get('run_number')}"
    job = payload.get("job_name") or payload.get("name", "unknown-job")
    build = payload.get("build_number") or payload.get("number", "?")
    return f"{job} #{build}"
