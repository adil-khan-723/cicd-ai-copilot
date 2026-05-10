"""
FastAPI router for the web UI.

Routes:
  GET  /              — dashboard HTML
  GET  /events        — SSE stream
  GET  /api/jobs      — list Jenkins jobs
  POST /api/setup     — save credentials
  POST /api/chat      — agent chat (streaming)
  POST /api/fix       — execute approved fix
  POST /api/commit    — commit generated pipeline to Jenkins
  POST /api/trigger   — trigger a Jenkins job manually
"""
import asyncio
import logging
import re
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
_jenkins_failure_poller_task: asyncio.Task | None = None


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


# ── Jenkins failure poller — fallback when Notification Plugin doesn't fire ──

async def _jenkins_failure_poller() -> None:
    """
    Poll all Jenkins jobs every 30s for newly-finished failed builds. Routes
    each new failure through the same analysis pipeline as the Notification
    Plugin webhook would. Dedups by (job, build) so a given failure analysis
    runs at most once.

    Why exists: Notification Plugin requires per-job config, can be silently
    misconfigured / blocked by network policy / version-skewed. The poller
    is best-effort but unconditional — works for any Jenkins setup.
    """
    import requests
    from config import get_settings

    seen: set[tuple[str, int]] = set()  # (job_name, build_number) already processed
    primed = False  # First scan: prime seen set with existing builds (don't re-analyze history)

    def _scan() -> list[tuple[str, int]]:
        """Return list of (job, build_number) for failed builds that finished since last scan."""
        s = get_settings()
        if not s.jenkins_url or not s.jenkins_token:
            return []
        try:
            # Get all jobs with their last completed build number + result
            r = requests.get(
                s.jenkins_url.rstrip('/') + '/api/json',
                auth=(s.jenkins_user or '', s.jenkins_token),
                params={"tree": "jobs[name,lastCompletedBuild[number,result]]"},
                timeout=8,
            )
            if r.status_code != 200:
                return []
            new_failures = []
            for job in r.json().get("jobs", []):
                name = job.get("name")
                last = job.get("lastCompletedBuild") or {}
                num = last.get("number")
                result = (last.get("result") or "").upper()
                if not name or not num:
                    continue
                key = (name, int(num))
                if result in ("FAILURE", "ABORTED", "UNSTABLE") and key not in seen:
                    new_failures.append(key)
                seen.add(key)
            return new_failures
        except Exception as e:
            logger.debug("failure poller scan error: %s", e)
            return []

    # Lazy-import to avoid circular import at module load
    from webhook.server import _process_notification_failure_sync

    while True:
        try:
            loop = asyncio.get_event_loop()
            failures = await loop.run_in_executor(None, _scan)
        except Exception as e:
            logger.warning("failure poller error: %s", e)
            failures = []

        if not primed:
            # First pass: only seed seen set, don't reprocess existing builds
            primed = True
            logger.info("Jenkins failure poller primed — tracking %d existing builds", len(seen))
        elif failures:
            for job, build in failures:
                logger.info("Poller detected new failure: %s #%s — running analysis", job, build)
                # Synthetic payload matches notification plugin shape so handler is identical
                payload = {
                    "name": job,
                    "build": {"number": build, "phase": "FINALIZED", "status": "FAILURE"},
                }
                try:
                    await loop.run_in_executor(
                        None, _process_notification_failure_sync, job, str(build), payload,
                    )
                except Exception as e:
                    logger.error("poller failed to process %s #%s: %s", job, build, e)

        await asyncio.sleep(30)

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
    jenkins_auth_method: str = "token"  # 'token' | 'password'


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


# ── Build history ──────────────────────────────────────────────────────────

@router.get("/api/build-history")
async def build_history(job: str, limit: int = 5):
    s = get_settings()
    if not s.jenkins_url or not s.jenkins_token:
        raise HTTPException(status_code=503, detail="Jenkins not configured")

    def _fetch():
        import requests as _req
        url = f"{s.jenkins_url.rstrip('/')}/job/{job}/api/json"
        params = {"tree": f"builds[number,result,timestamp,duration]{{0,{limit}}}"}
        r = _req.get(url, auth=(s.jenkins_user or '', s.jenkins_token or ''), params=params, timeout=8)
        r.raise_for_status()
        return r.json().get("builds", [])

    loop = asyncio.get_event_loop()
    try:
        builds = await loop.run_in_executor(None, _fetch)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"builds": builds}


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

def _mask_key(key: str) -> str:
    """Return 'sk-ant-•••...•••abcd' style masked preview. Never reveals full key."""
    if not key:
        return ""
    if len(key) <= 12:
        return "•" * len(key)
    return f"{key[:7]}•••...•••{key[-4:]}"


@router.get("/api/settings")
async def settings():
    from config import get_settings
    s = get_settings()
    return {
        "jenkins_url": s.jenkins_url,
        "jenkins_user": s.jenkins_user,
        "jenkins_auth_method": getattr(s, "jenkins_auth_method", "token"),
        "llm_provider": s.llm_provider,
        "llm_fallback_provider": getattr(s, "llm_fallback_provider", ""),
        "configured": bool(s.jenkins_url and s.jenkins_token),
        "webhook_secret_set": bool(s.webhook_secret),  # boolean only — never the value
        # LLM block — key never returned, only masked preview + bool
        "anthropic_configured": bool(s.anthropic_api_key),
        "anthropic_key_preview": _mask_key(s.anthropic_api_key),
        "anthropic_analysis_model": getattr(s, "anthropic_analysis_model", ""),
        "anthropic_generation_model": getattr(s, "anthropic_generation_model", ""),
        "ollama_base_url": getattr(s, "ollama_base_url", ""),
        "analysis_model": getattr(s, "analysis_model", ""),
        "generation_model": getattr(s, "generation_model", ""),
    }


class LLMConfigPayload(BaseModel):
    provider: str
    anthropic_api_key: str = ""
    anthropic_analysis_model: str = ""
    anthropic_generation_model: str = ""
    ollama_base_url: str = ""
    analysis_model: str = ""
    generation_model: str = ""


@router.post("/api/llm-settings")
async def save_llm_settings(payload: LLMConfigPayload):
    from ui.setup_handler import save_llm_config, SetupError
    try:
        save_llm_config(payload.model_dump())
    except SetupError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/api/llm/available-models")
async def available_models():
    """
    Enumerate all reachable LLM models across configured providers.
    Returns: { "models": [{"provider": "...", "model": "...", "online": bool, "label": "..."}], "default": {...} }
    Anthropic models listed only if API key configured + reachable.
    Ollama models listed only if /api/tags reachable.
    """
    from config import get_settings
    s = get_settings()
    models: list[dict] = []

    # Anthropic
    if s.anthropic_api_key:
        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=s.anthropic_api_key)
            page = client.models.list(limit=50)
            for m in page.data:
                models.append({
                    "provider": "anthropic",
                    "model": m.id,
                    "online": True,
                    "label": f"anthropic / {m.id}",
                })
        except Exception:
            # API down — still surface configured analysis/generation models so user can pick blindly
            for m in [s.anthropic_analysis_model, s.anthropic_generation_model]:
                if m:
                    models.append({
                        "provider": "anthropic", "model": m, "online": False,
                        "label": f"anthropic / {m} (offline)",
                    })

    # Ollama
    ollama_url = s.ollama_base_url or "http://localhost:11434"
    try:
        import requests as _req
        r = _req.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=3)
        if r.status_code == 200:
            for tag in r.json().get("models", []):
                name = tag.get("name", "")
                if name:
                    models.append({
                        "provider": "ollama", "model": name, "online": True,
                        "label": f"ollama / {name}",
                    })
    except Exception:
        for m in [s.analysis_model, s.generation_model]:
            if m:
                models.append({
                    "provider": "ollama", "model": m, "online": False,
                    "label": f"ollama / {m} (offline)",
                })

    return {
        "models": models,
        "default_provider": s.llm_provider,
        "default_analysis_model": (
            s.anthropic_analysis_model if s.llm_provider == "anthropic" else s.analysis_model
        ),
    }


# ── Jenkins profiles ───────────────────────────────────────────────────────

class ProfilePayload(BaseModel):
    alias: str
    jenkins_url: str
    jenkins_user: str
    jenkins_token: str
    jenkins_auth_method: str = "token"  # 'token' | 'password'


@router.get("/api/profiles")
async def get_profiles():
    from ui.profiles_store import list_profiles
    return {"profiles": list_profiles()}


@router.post("/api/profiles")
async def create_profile(payload: ProfilePayload):
    from ui.profiles_store import add_profile
    from ui.setup_handler import SetupError
    try:
        profile = add_profile(
            alias=payload.alias,
            jenkins_url=payload.jenkins_url,
            jenkins_user=payload.jenkins_user,
            jenkins_token=payload.jenkins_token,
            jenkins_auth_method=payload.jenkins_auth_method,
        )
        return {"ok": True, "profile": profile}
    except SetupError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/api/profiles/{profile_id}/activate")
async def activate_profile(profile_id: str):
    from ui.profiles_store import activate_profile
    ok = activate_profile(profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True}


@router.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    from ui.profiles_store import delete_profile
    ok = delete_profile(profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True}


@router.patch("/api/profiles/{profile_id}")
async def rename_profile(profile_id: str, body: dict):
    from ui.profiles_store import update_profile
    alias = body.get("alias", "").strip()
    if not alias:
        raise HTTPException(status_code=422, detail="alias is required")
    ok = update_profile(profile_id, alias)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True}


# ── LLM API key manager (multi-key, multi-provider) ────────────────────────

class LLMKeyPayload(BaseModel):
    name: str
    provider: str  # 'anthropic' (more later)
    key: str


@router.get("/api/llm-keys")
async def list_llm_keys():
    from ui.llm_keys_store import list_keys
    return {"keys": list_keys()}


@router.post("/api/llm-keys")
async def create_llm_key(payload: LLMKeyPayload):
    from ui.llm_keys_store import add_key
    try:
        key = add_key(payload.name, payload.provider, payload.key)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True, "key": key}


@router.post("/api/llm-keys/{key_id}/activate")
async def activate_llm_key(key_id: str):
    from ui.llm_keys_store import activate_key
    if not activate_key(key_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"ok": True}


@router.delete("/api/llm-keys/{key_id}")
async def delete_llm_key(key_id: str):
    from ui.llm_keys_store import delete_key
    ok, err = delete_key(key_id)
    if not ok:
        # 409 if blocked (active), 404 if missing
        status = 404 if "not found" in err.lower() else 409
        raise HTTPException(status_code=status, detail=err)
    return {"ok": True}


# ── Credential test-connection ─────────────────────────────────────────────

class TestConnectionPayload(BaseModel):
    provider: str  # "jenkins" | "anthropic" | "ollama"
    # Optional: test an unsaved key (lets user click Test before Save).
    # Never stored — used only for the test call.
    api_key: str = ""
    base_url: str = ""
    # Optional unsaved Jenkins creds (lets user click Test before Save in setup).
    # If url is provided, these override saved settings for the test only.
    jenkins_url: str = ""
    jenkins_user: str = ""
    jenkins_token: str = ""
    jenkins_auth_method: str = "token"  # 'token' | 'password' — both flow as basic auth


@router.post("/api/secrets/test-connection")
async def test_connection(payload: TestConnectionPayload):
    """
    Test connectivity for a provider using the current settings.
    Stores nothing. Returns scrubbed error detail on failure.
    """
    from copilot.secrets_manager import scrub
    from config import get_settings
    import requests as _req

    s = get_settings()
    provider = payload.provider.lower().strip()

    if provider == "jenkins":
        def _ping():
            # Prefer unsaved payload creds (Test before Save in setup wizard);
            # else fall back to saved settings.
            url = (payload.jenkins_url or s.jenkins_url or "").strip()
            user = (payload.jenkins_user or s.jenkins_user or "").strip()
            token = (payload.jenkins_token or s.jenkins_token or "").strip()
            if not url or not token:
                return False, "Jenkins URL and credential required."
            if not (url.startswith("http://") or url.startswith("https://")):
                return False, "Jenkins URL must start with http:// or https://."
            try:
                r = _req.get(
                    url.rstrip("/") + "/api/json",
                    auth=(user, token),
                    timeout=6,
                )
                if r.status_code == 401 or r.status_code == 403:
                    return False, f"Authentication failed (HTTP {r.status_code}) — check user and {'token' if payload.jenkins_auth_method == 'token' else 'password'}."
                if r.status_code == 404:
                    return False, "HTTP 404 — URL reachable but /api/json missing. Is this really Jenkins?"
                if r.status_code >= 500:
                    return False, scrub(f"Jenkins error HTTP {r.status_code}.")
                if r.status_code >= 400:
                    return False, scrub(f"HTTP {r.status_code}: {r.text[:120]}")
                version = r.headers.get("X-Jenkins", "")
                msg = f"Jenkins reachable (v{version})." if version else "Jenkins reachable."
                return True, msg
            except _req.exceptions.ConnectTimeout:
                return False, "Connection timed out — host unreachable or firewalled."
            except _req.exceptions.ConnectionError as e:
                return False, scrub(f"Connection failed: {e}")
            except Exception as e:
                return False, scrub(str(e))

        loop = asyncio.get_event_loop()
        ok, detail = await loop.run_in_executor(None, _ping)
        return {"ok": ok, "detail": detail}

    if provider == "anthropic":
        def _check():
            try:
                # If user supplied an unsaved key in payload (Test before Save), use it.
                # Else fall back to whatever's in settings.
                test_key = payload.api_key.strip() or s.anthropic_api_key
                if not test_key:
                    return False, "No API key supplied or saved."
                if not test_key.startswith("sk-"):
                    return False, "Key must start with 'sk-'."
                import anthropic as _anthropic
                client = _anthropic.Anthropic(api_key=test_key)
                # Cheapest reachability check: list models endpoint
                try:
                    client.models.list(limit=1)
                    return True, "Anthropic reachable — key valid."
                except _anthropic.AuthenticationError:
                    return False, "Authentication failed — key rejected."
                except Exception as e:
                    return False, scrub(f"Request failed: {e}")
            except ImportError:
                return False, "anthropic SDK not installed."
            except Exception as e:
                return False, scrub(str(e))

        loop = asyncio.get_event_loop()
        ok, detail = await loop.run_in_executor(None, _check)
        return {"ok": ok, "detail": detail}

    if provider == "ollama":
        def _check():
            try:
                from providers.ollama_provider import OllamaProvider
                available = OllamaProvider().is_available()
                return available, "Ollama reachable." if available else "Ollama not reachable — is it running?"
            except Exception as e:
                return False, scrub(str(e))

        loop = asyncio.get_event_loop()
        ok, detail = await loop.run_in_executor(None, _check)
        return {"ok": ok, "detail": detail}

    return {"ok": False, "detail": "Unknown provider — use 'jenkins', 'anthropic', or 'ollama'."}


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
    bad_image: Optional[str] = None
    correct_image: Optional[str] = None
    credential_type: Optional[str] = None
    secret_value: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_username: Optional[str] = None
    private_key: Optional[str] = None
    skip_retrigger: Optional[str] = None


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
    if payload.bad_image:
        kwargs["bad_image"] = payload.bad_image
    if payload.correct_image:
        kwargs["correct_image"] = payload.correct_image
    if payload.credential_type:
        kwargs["credential_type"] = payload.credential_type
    if payload.secret_value:
        kwargs["secret_value"] = payload.secret_value
    if payload.username:
        kwargs["username"] = payload.username
    if payload.password:
        kwargs["password"] = payload.password
    if payload.ssh_username:
        kwargs["ssh_username"] = payload.ssh_username
    if payload.private_key:
        kwargs["private_key"] = payload.private_key
    if payload.skip_retrigger == "true":
        kwargs["skip_retrigger"] = True

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

    # Snapshot the next build number before the fix triggers a new run
    def _get_next_build_number(job: str) -> int | None:
        import requests as _req
        from config import get_settings as _gs
        _s = _gs()
        if not _s.jenkins_url:
            return None
        try:
            r = _req.get(
                f"{_s.jenkins_url.rstrip('/')}/job/{job}/api/json?tree=nextBuildNumber",
                auth=(_s.jenkins_user or '', _s.jenkins_token or ''),
                timeout=5,
            )
            return r.json().get("nextBuildNumber")
        except Exception:
            return None

    loop = asyncio.get_event_loop()
    next_build = await loop.run_in_executor(None, _get_next_build_number, payload.job_name)

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
        "next_build": next_build,
    })
    return {
        "success": result.success,
        "fix_type": result.fix_type,
        "detail": result.detail,
        "next_build": next_build,
    }


# ── Audit log ─────────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 40) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:max_len].rstrip("-")


class CommitPayload(BaseModel):
    platform: str
    content: str
    description: str
    apply_to_jenkins: bool = False
    job_name: Optional[str] = None


@router.post("/api/commit")
async def commit_pipeline(payload: CommitPayload):
    from copilot.jenkins_configurator import create_job
    from copilot.credential_extractor import extract_credential_ids
    from copilot.credential_checker import get_missing_credentials

    job_name = payload.job_name.strip() if payload.job_name and payload.job_name.strip() else _slugify(payload.description)

    if payload.platform == "jenkins" and payload.apply_to_jenkins:
        try:
            job_url = await asyncio.get_event_loop().run_in_executor(
                None, create_job, job_name, payload.content, payload.description
            )
            cred_ids = extract_credential_ids(payload.content)
            logger.info("commit_pipeline: extracted cred_ids=%s from job %s", cred_ids, job_name)
            missing = await asyncio.get_event_loop().run_in_executor(
                None, get_missing_credentials, cred_ids
            )
            logger.info("commit_pipeline: missing_credentials=%s for job %s", missing, job_name)
            return {
                "success": True,
                "job_name": job_name,
                "job_url": job_url,
                "detail": "Job created",
                "missing_credentials": missing,
            }
        except Exception as exc:
            logger.error("commit_pipeline error: %s", exc)
            return {"success": False, "job_name": job_name, "job_url": None, "detail": str(exc), "missing_credentials": []}

    return {"success": True, "job_name": job_name, "job_url": None, "detail": "Saved (not applied to Jenkins)", "missing_credentials": []}


@router.get("/api/audit")
async def audit_log(limit: int = 20):
    from agent.audit_log import read_recent
    entries = read_recent(limit)
    return {"entries": list(reversed(entries))}  # most recent first


# ── Inject webhook post blocks into a Jenkins job ─────────────────────────

class InjectWebhookPayload(BaseModel):
    job_name: str


class ReanalyzePayload(BaseModel):
    job: str
    build: str
    provider_override: str = ""
    model_override: str = ""


@router.post("/api/reanalyze")
async def reanalyze(payload: ReanalyzePayload):
    """
    Re-run analysis on a previously-analyzed build with a different model.
    Reuses the cached context (no Jenkins re-fetch). Emits a fresh
    analysis_complete event so the UI updates the card in place.

    EventBus dedup logic for analysis_complete (drop duplicate per job+build)
    is bypassed here because we mark the event with a fresh suffix below
    by including model_used (UI keys card by job+build, not full event).
    """
    from analyzer.llm_client import analyze
    from webhook.server import _last_context_by_build, _filter_potential_issues
    from ui.event_bus import bus

    key = (str(payload.job), str(payload.build))
    saved = _last_context_by_build.get(key)
    if not saved:
        raise HTTPException(
            status_code=404,
            detail=f"No saved context for {payload.job} #{payload.build}. Trigger a fresh build first.",
        )

    loop = asyncio.get_event_loop()
    analysis = await loop.run_in_executor(
        None,
        lambda: analyze(
            saved["context"],
            provider_override=payload.provider_override,
            model_override=payload.model_override,
        ),
    )

    # Re-run the same potential_issues filter so the new analysis carries them
    report = saved["verification"]
    settings = get_settings()
    jenkins_auth = (settings.jenkins_user, settings.jenkins_token) if settings.jenkins_token else None
    primary_cred_id = ""
    if analysis.get("fix_type") == "configure_credential" and report.missing_credentials:
        primary_cred_id = report.missing_credentials[0]
    primary_tool_ref = ""
    if analysis.get("fix_type") == "configure_tool" and report.mismatched_tools:
        primary_tool_ref = report.mismatched_tools[0].referenced
    filtered = _filter_potential_issues(
        analysis.get("potential_issues", []),
        report,
        primary_fix_type=analysis.get("fix_type", ""),
        primary_cred_id=primary_cred_id,
        primary_tool_ref=primary_tool_ref,
        jenkins_url=settings.jenkins_url or "",
        jenkins_auth=jenkins_auth,
    )

    # EventBus dedups analysis_complete by (job, build). Bus.clear_history is too
    # destructive — just clear the prior analysis_complete for this build.
    bus._history = type(bus._history)(
        (e for e in bus._history
         if not (e.get("type") == "analysis_complete"
                 and str(e.get("job")) == str(payload.job)
                 and str(e.get("build")) == str(payload.build))),
        maxlen=bus._history.maxlen,
    )

    bus.publish({
        "type": "analysis_complete",
        "job": payload.job,
        "build": payload.build,
        "failed_stage": "",
        "root_cause": analysis.get("root_cause", ""),
        "fix_suggestion": analysis.get("fix_suggestion", ""),
        "steps": analysis.get("steps", []),
        "fix_type": analysis.get("fix_type"),
        "confidence": analysis.get("confidence", 0),
        "log_excerpt": "",
        "bad_step": analysis.get("bad_step") or analysis.get("bad_line"),
        "correct_step": analysis.get("correct_step") or analysis.get("correct_line"),
        "bad_image": analysis.get("bad_image"),
        "correct_image": analysis.get("correct_image"),
        "credential_type": analysis.get("credential_type"),
        "potential_issues": filtered,
        "model_used": analysis.get("model_used", ""),
        "provider_used": analysis.get("provider_used", ""),
        "key_name": analysis.get("key_name", ""),
        "reanalyzed": True,
    })
    return {
        "ok": True,
        "model_used": analysis.get("model_used", ""),
        "provider_used": analysis.get("provider_used", ""),
        "key_name": analysis.get("key_name", ""),
    }


@router.post("/api/feed/clear")
async def clear_feed():
    """Wipe SSE history so browsers reconnecting won't replay old build events."""
    from ui.event_bus import bus
    bus.clear_history()
    return {"ok": True}


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

