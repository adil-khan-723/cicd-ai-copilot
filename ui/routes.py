"""
FastAPI router for the web UI.

Routes:
  GET  /              — dashboard HTML
  GET  /events        — SSE stream
  GET  /api/jobs      — list Jenkins jobs
  POST /api/setup     — save credentials
  POST /api/chat      — agent chat (streaming)
  POST /api/fix       — execute approved fix
  POST /api/commit    — commit pipeline file to GitHub + apply to Jenkins
  POST /api/trigger   — trigger a Jenkins job manually
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

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
    github_repo: str
    github_token: str
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


# ── Agent chat ─────────────────────────────────────────────────────────────

class ChatPayload(BaseModel):
    message: str


@router.post("/api/chat")
async def chat(payload: ChatPayload):
    from ui.chat_handler import handle_chat

    def generate():
        for chunk in handle_chat(payload.message):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


# ── Fix execution ──────────────────────────────────────────────────────────

class FixPayload(BaseModel):
    fix_type: str
    job_name: str
    build_number: str = "0"


@router.post("/api/fix")
async def fix(payload: FixPayload):
    from agent.fix_executor import execute_fix
    from agent.audit_log import log_fix

    result = await asyncio.get_event_loop().run_in_executor(
        None, execute_fix, payload.fix_type, payload.job_name, payload.build_number
    )
    log_fix(
        fix_type=payload.fix_type,
        triggered_by="web-ui",
        job_name=payload.job_name,
        build_number=payload.build_number,
        result="success" if result.success else "failed",
        confidence=None,
    )
    from ui.event_bus import bus
    bus.publish({
        "type": "fix_result",
        "job": payload.job_name,
        "build": payload.build_number,
        "fix_type": payload.fix_type,
        "success": result.success,
        "detail": result.detail,
    })
    return {"success": result.success, "fix_type": result.fix_type, "detail": result.detail}


# ── Commit pipeline file ───────────────────────────────────────────────────

class CommitPayload(BaseModel):
    platform: str
    content: str
    description: str
    repo: Optional[str] = None
    apply_to_jenkins: bool = True


@router.post("/api/commit")
async def commit(payload: CommitPayload):
    from copilot.repo_committer import commit_pipeline_file
    from config import get_settings

    settings = get_settings()
    repo = payload.repo or settings.github_repo
    if not repo:
        raise HTTPException(
            status_code=422,
            detail="No GitHub repo configured. Run setup first.",
        )

    try:
        file_path, commit_url = await asyncio.get_event_loop().run_in_executor(
            None, commit_pipeline_file,
            repo, payload.platform, payload.content, payload.description,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    jenkins_result = None
    if payload.apply_to_jenkins and payload.platform == "jenkins":
        from copilot.jenkins_configurator import create_job
        job_name = repo.split("/")[-1]
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, create_job, job_name, payload.content
            )
            jenkins_result = {"ok": True, "job": job_name}
        except Exception as e:
            jenkins_result = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "file_path": file_path,
        "commit_url": commit_url,
        "jenkins": jenkins_result,
    }
