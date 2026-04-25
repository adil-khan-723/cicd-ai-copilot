"""
FastAPI router for the web UI.

Routes:
  GET  /              — dashboard HTML
  GET  /events        — SSE stream
  GET  /api/jobs      — list Jenkins jobs
  POST /api/setup     — save credentials
  POST /api/chat      — agent chat (streaming)
  POST /api/fix       — execute approved fix
  POST /api/trigger   — trigger a Jenkins job manually
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

import jenkins
from config import get_settings

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Jenkins health monitor ──────────────────────────────────────────────────

_jenkins_monitor_task: asyncio.Task | None = None


async def _jenkins_health_monitor() -> None:
    """Poll Jenkins every 10s; push jenkins_status SSE event only on change."""
    import requests
    from config import get_settings
    from ui.event_bus import bus

    last: bool | None = None

    def _ping() -> bool:
        s = get_settings()
        if not s.jenkins_url:
            return False
        try:
            r = requests.get(
                s.jenkins_url.rstrip('/') + '/api/json',
                auth=(s.jenkins_user or '', s.jenkins_token or ''),
                timeout=5,
            )
            return r.status_code < 500
        except Exception:
            return False

    while True:
        try:
            loop = asyncio.get_event_loop()
            ok = await asyncio.wait_for(loop.run_in_executor(None, _ping), timeout=6.0)
        except Exception:
            ok = False

        if ok is not last:
            last = ok
            bus.publish({"type": "jenkins_status", "ok": ok})
            logger.info("Jenkins status changed → %s", "up" if ok else "down")

        await asyncio.sleep(10)

_STATIC_DIR = Path(__file__).parent / "static"


# ── Dashboard ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    html = (_STATIC_DIR / "index.html").read_text()
    return HTMLResponse(content=html)


# ── SSE event stream ───────────────────────────────────────────────────────

@router.get("/events")
async def events():
    from ui.event_bus import bus

    async def stream():
        yield "retry: 3000\n\n"
        async for chunk in bus.subscribe():
            yield chunk

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Setup wizard ───────────────────────────────────────────────────────────

class SetupPayload(BaseModel):
    jenkins_url: str
    jenkins_user: str
    jenkins_token: str


@router.post("/api/setup")
async def setup(payload: SetupPayload):
    from ui.setup_handler import save_credentials, SetupError
    try:
        save_credentials(payload.model_dump())
        return {"ok": True}
    except SetupError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Jenkins health ─────────────────────────────────────────────────────────

@router.get("/api/health")
async def health():
    """Fast liveness check — HTTP ping to Jenkins /api/json with 5s timeout."""
    import requests
    from config import get_settings

    def _ping():
        s = get_settings()
        if not s.jenkins_url:
            return False
        try:
            url = s.jenkins_url.rstrip('/') + '/api/json'
            r = requests.get(
                url,
                auth=(s.jenkins_user or '', s.jenkins_token or ''),
                timeout=5,
            )
            return r.status_code < 500
        except Exception:
            return False

    loop = asyncio.get_event_loop()
    try:
        ok = await asyncio.wait_for(
            loop.run_in_executor(None, _ping),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        ok = False

    return {"ok": ok}


# ── Jenkins jobs ───────────────────────────────────────────────────────────

@router.get("/api/jobs")
async def jobs():
    from ui.jobs_handler import get_jenkins_jobs
    result = await asyncio.get_event_loop().run_in_executor(None, get_jenkins_jobs)
    return result


class TriggerPayload(BaseModel):
    job_name: str


@router.post("/api/trigger")
async def trigger(payload: TriggerPayload):
    from ui.jobs_handler import trigger_job
    result = await asyncio.get_event_loop().run_in_executor(
        None, trigger_job, payload.job_name
    )
    return result


# ── Build log ──────────────────────────────────────────────────────────────

@router.get("/api/build-log")
async def build_log(job: str, build: int):
    s = get_settings()
    if not s.jenkins_url or not s.jenkins_token:
        raise HTTPException(status_code=503, detail="Jenkins not configured")

    def _fetch():
        server = jenkins.Jenkins(
            s.jenkins_url,
            username=s.jenkins_user or "",
            password=s.jenkins_token,
        )
        try:
            return server.get_build_console_output(job, build)
        except jenkins.NotFoundException:
            return None
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not fetch log from Jenkins: {e}")

    loop = asyncio.get_event_loop()
    try:
        log = await loop.run_in_executor(None, _fetch)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch log from Jenkins: {e}")

    if log is None:
        raise HTTPException(status_code=404, detail="Build not found")

    return {"log": log}


# ── Agent chat ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatPayload(BaseModel):
    message: str
    history: Optional[list[ChatMessage]] = None


@router.post("/api/chat")
async def chat(payload: ChatPayload):
    from ui.chat_handler import handle_chat

    history = [m.model_dump() for m in payload.history] if payload.history else None

    def generate():
        for chunk in handle_chat(payload.message, history=history):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


# ── Settings (read active config for UI bootstrap) ─────────────────────────

@router.get("/api/settings")
async def settings():
    from config import get_settings
    s = get_settings()
    return {
        "jenkins_url": s.jenkins_url,
        "jenkins_user": s.jenkins_user,
        "llm_provider": s.llm_provider,
        "configured": bool(s.jenkins_url and s.jenkins_token),
    }


# ── Fix execution ──────────────────────────────────────────────────────────

class FixPayload(BaseModel):
    fix_type: str
    job_name: str
    build_number: str = "0"
    referenced_name: Optional[str] = None
    configured_name: Optional[str] = None
    credential_id: Optional[str] = None
    bad_step: Optional[str] = None
    correct_step: Optional[str] = None


@router.post("/api/fix")
async def fix(payload: FixPayload):
    from agent.fix_executor import execute_fix
    from agent.audit_log import log_fix
    from ui.event_bus import bus

    kwargs = {}
    if payload.referenced_name:
        kwargs["referenced_name"] = payload.referenced_name
    if payload.configured_name:
        kwargs["configured_name"] = payload.configured_name
    if payload.credential_id:
        kwargs["credential_id"] = payload.credential_id
    if payload.bad_step:
        kwargs["bad_step"] = payload.bad_step
    if payload.correct_step:
        kwargs["correct_step"] = payload.correct_step

    # Fallback: for configure_tool with missing names, parse from console log
    if payload.fix_type == "configure_tool" and (not kwargs.get("referenced_name") or not kwargs.get("configured_name")):
        import re as _re, requests as _req
        from config import get_settings as _gs
        _s = _gs()
        try:
            log = _req.get(
                f"{_s.jenkins_url}/job/{payload.job_name}/{payload.build_number}/consoleText",
                auth=(_s.jenkins_user, _s.jenkins_token), timeout=10,
            ).text
            m = _re.search(
                r'Tool type "[^"]+" does not have an install of "([^"]+)"[^"]*"([^"]+)"',
                log, _re.IGNORECASE,
            )
            if m and m.group(2).lower() != "null":
                kwargs["referenced_name"] = m.group(1)
                kwargs["configured_name"] = m.group(2)
        except Exception:
            pass

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: execute_fix(payload.fix_type, payload.job_name, payload.build_number, **kwargs)
    )

    log_fix(
        fix_type=payload.fix_type,
        triggered_by="web-ui",
        job_name=payload.job_name,
        build_number=payload.build_number,
        result="success" if result.success else "failed",
        confidence_at_trigger=0.0,
    )

    bus.publish({
        "type": "fix_result",
        "job": payload.job_name,
        "build": payload.build_number,
        "fix_type": payload.fix_type,
        "success": result.success,
        "detail": result.detail,
    })
    return {"success": result.success, "fix_type": result.fix_type, "detail": result.detail}


# ── Inject webhook post blocks into a Jenkins job ─────────────────────────

class InjectWebhookPayload(BaseModel):
    job_name: str


@router.post("/api/inject-webhook")
async def inject_webhook(payload: InjectWebhookPayload):
    result = await asyncio.get_event_loop().run_in_executor(
        None, _inject_webhook_blocks, payload.job_name
    )
    return result


def _inject_webhook_blocks(job_name: str) -> dict:
    """
    Adds the Jenkins Notification Plugin property to a job so it sends
    build events to /webhook/jenkins-notification on every build finish.
    No post blocks in Jenkinsfiles needed.
    """
    import xml.etree.ElementTree as ET
    from config import get_settings

    settings = get_settings()
    if not settings.jenkins_url or not settings.jenkins_token:
        return {"ok": False, "detail": "Jenkins not configured."}

    NOTIFICATION_URL = "http://host.docker.internal:8000/webhook/jenkins-notification"
    NOTIFICATION_XML = f"""<com.tikal.hudson.plugins.notification.HudsonNotificationProperty plugin="notification">
      <endpoints>
        <com.tikal.hudson.plugins.notification.Endpoint>
          <protocol>HTTP</protocol>
          <format>JSON</format>
          <urlInfo>
            <urlOrId>{NOTIFICATION_URL}</urlOrId>
            <urlType>PUBLIC</urlType>
          </urlInfo>
          <event>finalized</event>
          <timeout>30000</timeout>
          <loglines>0</loglines>
          <retries>3</retries>
        </com.tikal.hudson.plugins.notification.Endpoint>
      </endpoints>
    </com.tikal.hudson.plugins.notification.HudsonNotificationProperty>"""

    try:
        import jenkins as jenkins_lib
        server = jenkins_lib.Jenkins(
            settings.jenkins_url,
            username=settings.jenkins_user,
            password=settings.jenkins_token,
        )
        config_xml = server.get_job_config(job_name)
    except Exception as e:
        return {"ok": False, "detail": f"Could not fetch job config: {e}"}

    try:
        tree = ET.fromstring(config_xml)

        # Already wired?
        existing = tree.find('.//com.tikal.hudson.plugins.notification.HudsonNotificationProperty')
        if existing is not None:
            url_el = existing.find('.//urlOrId')
            if url_el is not None and NOTIFICATION_URL in (url_el.text or ""):
                return {"ok": True, "detail": "Already wired up — nothing to do.", "already": True}
            # Stale/wrong URL — remove and replace
            props = tree.find('properties')
            if props is not None:
                props.remove(existing)

        props = tree.find('properties')
        if props is None:
            props = ET.SubElement(tree, 'properties')
        props.append(ET.fromstring(NOTIFICATION_XML))

        new_config = ET.tostring(tree, encoding='unicode', xml_declaration=False)
        server.reconfig_job(job_name, "<?xml version='1.1' encoding='UTF-8'?>\n" + new_config)
        return {"ok": True, "detail": "Notification plugin wired up successfully."}

    except Exception as e:
        return {"ok": False, "detail": f"Failed to wire up: {e}"}


# ── Commit pipeline file ───────────────────────────────────────────────────

